"""
F5: 自适应出题推荐引擎 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import (
    Student, Question, StudentAnswer, ExamRecord,
    get_db, RecordType, Difficulty, AuditStatus, BarrierType, QuestionSource
)

router = APIRouter()


class PracticeTask(BaseModel):
    """练习任务"""
    practice_id: str
    student_id: str
    student_name: str
    knowledge_points: List[str]
    target_barrier: str  # 目标障碍类型
    question_count: int
    difficulty: str  # AI判断为"稍微超出当前水平"
    deadline: str
    status: str  # pending/completed/overdue


class PracticeQuestion(BaseModel):
    """练习题目"""
    question_id: str
    content: str
    options: Optional[List[str]] = None
    estimated_time: int  # 预计用时(分钟)


class StudentPracticeResponse(BaseModel):
    """学生练习响应"""
    practice_id: str
    student_id: str
    knowledge_points: List[str]
    questions: List[PracticeQuestion]
    total_questions: int
    estimated_time: int


class PracticeSubmitRequest(BaseModel):
    """提交练习请求"""
    practice_id: str
    student_id: str
    answers: List[dict]  # [{question_id, answer}]


class PracticeResult(BaseModel):
    """练习结果"""
    practice_id: str
    student_id: str
    correct_count: int
    total_count: int
    accuracy: float
    difficulty_appropriate: bool  # 学生反馈"不太难也不太简单"
    barrier_change: Optional[dict]  # 障碍类型变化


class PracticeAssignRequest(BaseModel):
    """布置练习请求"""
    class_id: str
    knowledge_points: List[str]
    target_barrier: Optional[str] = None  # 概念理解/审题障碍/表述障碍
    question_count: int = 10
    deadline: Optional[str] = None


def _calculate_zpd_difficulty(student_id: str, db: Session) -> str:
    """计算最近发展区难度
    读取学生最近10次答题正确率:
      < 40% → easy
      40-70% → medium
      > 70% → hard
    """
    recent_answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id
    ).order_by(StudentAnswer.answered_at.desc()).limit(30).all()

    if not recent_answers:
        return "medium"  # 默认

    correct = sum(1 for a in recent_answers if a.is_correct)
    rate = correct / len(recent_answers)
    if rate < 0.4:
        return "easy"
    elif rate <= 0.7:
        return "medium"
    else:
        return "hard"


def _get_weak_kps(student_id: str, db: Session, top_n: int = 3) -> List[str]:
    """从学生错题统计中提取薄弱知识点 TOP N"""
    from collections import Counter
    wrong_answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.is_correct == False,
    ).all()

    kp_counter = Counter()
    for ans in wrong_answers:
        question = db.query(Question).filter(
            Question.question_id == ans.question_id
        ).first()
        if question and question.knowledge_points:
            for kp in question.knowledge_points:
                kp_counter[kp] += 1

    return [kp for kp, _ in kp_counter.most_common(top_n)]


def _get_dominant_barrier(student_id: str, db: Session) -> str:
    """获取学生主要障碍类型"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student and student.barrier_type and isinstance(student.barrier_type, dict):
        bt = student.barrier_type
        return max(bt, key=bt.get)
    return "concept"


@router.post("/assign")
async def assign_practice(request: PracticeAssignRequest, db: Session = Depends(get_db)):
    """
    布置自适应练习
    为每个学生根据障碍类型 + 最近发展区 + 薄弱知识点 生成个性化练习
    """
    practice_id = f"practice_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    students = db.query(Student).filter(Student.class_id == request.class_id).all()

    if not students:
        return {"success": False, "message": "班级无学生"}

    from app.services.llm_service import llm_service

    import traceback as _tb
    assigned = []
    for student in students[:5]:  # 限制批次，避免LLM过载
        try:
            barrier = _get_dominant_barrier(student.student_id, db)
            zpd_diff = _calculate_zpd_difficulty(student.student_id, db)
            weak_kps = _get_weak_kps(student.student_id, db)
            kps = weak_kps if weak_kps else request.knowledge_points

            if not kps:
                continue

            # 尝试从题库获取相似真题作为RAG上下文
            rag_context = None
            try:
                from app.services.exam_bank import exam_bank_service
                rag_context = exam_bank_service.find_similar_questions(
                    knowledge_points=kps, difficulty=zpd_diff, limit=3
                )
                rag_context = [
                    {"content": q.content, "answer": q.answer, "knowledge_points": q.knowledge_points}
                    for q in rag_context
                ]
            except Exception:
                pass

            result = llm_service.generate_questions(
                knowledge_points=kps,
                difficulty=zpd_diff,
                quantity=request.question_count,
                question_types=["choice"],
                rag_context=rag_context,
            )

            if result.get("success"):
                content = result.get("content", "{}")
                import re as _re, json as _json
                _match = _re.search(r'\{[\s\S]*\}', content)
                try:
                    q_data = _json.loads(_match.group()) if _match else {}
                    questions = q_data.get("questions", [])
                except _json.JSONDecodeError:
                    questions = []

                if questions:
                    exam_record = ExamRecord(
                        record_id=f"{practice_id}_{student.student_id}",
                        class_id=request.class_id,
                        name=f"自适应练习-{student.name}",
                        type=RecordType.PRACTICE,
                        total_students=1,
                        present_students=1,
                        exam_date=datetime.utcnow(),
                    )
                    db.add(exam_record)

                    for i, q in enumerate(questions):
                        question = Question(
                            question_id=f"q_{practice_id}_{student.student_id}_{i}",
                            record_id=exam_record.record_id,
                            content=q.get("content", ""),
                            options=q.get("options"),
                            answer=q.get("answer", ""),
                            analysis=q.get("analysis", ""),
                            knowledge_points=q.get("knowledge_points", kps),
                            difficulty=Difficulty.MEDIUM,
                            source=QuestionSource.AI_GENERATED,
                            audit_status=AuditStatus.PASSED,
                        )
                        db.add(question)

                    assigned.append({
                        "student_id": student.student_id,
                        "student_name": student.name,
                        "zpd_difficulty": zpd_diff,
                        "barrier": barrier,
                        "weak_kps": weak_kps,
                        "question_count": len(questions),
                    })
            else:
                print(f"[Practice] LLM failed for {student.name}: {result.get('error','?')}")
        except Exception as e:
            print(f"[Practice] Error for {student.name}: {e}")
            _tb.print_exc()

    if assigned:
        db.commit()

    return {
        "success": True,
        "practice_id": practice_id,
        "assigned_count": len(assigned),
        "assigned": assigned,
        "message": f"已为 {len(assigned)} 名学生生成个性化练习",
    }


@router.get("/student/{student_id}/tasks")
async def get_student_practice_tasks(student_id: str, db: Session = Depends(get_db)):
    """
    获取学生今日练习任务
    """
    try:
        # 查询学生的练习记录
        student = db.query(Student).filter(Student.student_id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

        # 查询学生的练习记录(PRACTICE) + 已发布考试(EXAM)
        from sqlalchemy import or_
        practices = db.query(ExamRecord).filter(
            ExamRecord.class_id == student.class_id,
            or_(
                ExamRecord.type == RecordType.PRACTICE,
                ExamRecord.type == RecordType.EXAM
            )
        ).all()

        tasks = []
        for p in practices:
            # 解析question_stats（可能是dict或JSON字符串）
            stats = p.question_stats
            if isinstance(stats, str):
                try:
                    import json as json_lib
                    stats = json_lib.loads(stats)
                except:
                    stats = None

            # EXAM 需要 published=true, PRACTICE 不需要
            if p.type == RecordType.EXAM:
                if not stats or not stats.get("published"):
                    continue

            # 统计题目数量：优先查 Question 表，回退到 stats 中的 metadata
            question_count = db.query(Question).filter(
                Question.record_id == p.record_id
            ).count()
            if question_count == 0 and isinstance(stats, dict):
                question_count = stats.get("question_count", 0)

            # PRACTICE 从 question_stats 获取 kp，EXAM 可能没有 kp
            if isinstance(stats, dict) and "knowledge_points" in stats:
                knowledge_points = stats.get("knowledge_points", [])
            else:
                knowledge_points = []

            # 检查学生是否已提交过
            submitted = db.query(StudentAnswer).filter(
                StudentAnswer.exam_record_id == p.record_id,
                StudentAnswer.student_id == student_id
            ).count()

            tasks.append(PracticeTask(
                practice_id=p.record_id,
                student_id=student_id,
                student_name=student.name,
                knowledge_points=knowledge_points,
                target_barrier="concept",
                question_count=question_count,
                difficulty="medium",
                deadline=p.exam_date.strftime("%Y-%m-%d %H:%M") if p.exam_date else "",
                status="completed" if submitted > 0 else "pending"
            ))

        return {
            "student_id": student_id,
            "student_name": student.name,
            "tasks": tasks
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取练习任务失败: {str(e)}")


@router.get("/student/{student_id}/practice/{practice_id}", response_model=StudentPracticeResponse)
async def get_practice_content(student_id: str, practice_id: str, db: Session = Depends(get_db)):
    """
    获取练习内容
    """
    # 查询练习记录
    practice = db.query(ExamRecord).filter(
        ExamRecord.record_id == practice_id
    ).first()

    if not practice:
        raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")

    # 查询练习题目
    questions = db.query(Question).filter(
        Question.record_id == practice_id
    ).all()

    # 查询学生已完成的答题
    completed_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == practice_id,
        StudentAnswer.student_id == student_id
    ).all()

    completed_question_ids = {a.question_id for a in completed_answers}

    # 只返回未完成的题目
    pending_questions = [q for q in questions if q.question_id not in completed_question_ids]

    return StudentPracticeResponse(
        practice_id=practice_id,
        student_id=student_id,
        knowledge_points=practice.question_stats.get("knowledge_points", []) if isinstance(practice.question_stats, dict) else [],
        questions=[
            PracticeQuestion(
                question_id=q.question_id,
                content=q.content,
                options=q.options,
                estimated_time=3
            )
            for q in pending_questions
        ],
        total_questions=len(questions),
        estimated_time=len(pending_questions) * 3
    )


@router.post("/submit", response_model=PracticeResult)
async def submit_practice(request: PracticeSubmitRequest, db: Session = Depends(get_db)):
    """
    提交练习答案
    立即返回答题结果+解析
    """
    try:
        # 获取学生信息
        student = db.query(Student).filter(Student.student_id == request.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail=f"学生 {request.student_id} 不存在")

        correct_count = 0
        total_count = len(request.answers)

        # 判定答案并保存
        for ans in request.answers:
            question = db.query(Question).filter(
                Question.question_id == ans.get("question_id")
            ).first()

            if not question:
                continue

            student_answer = ans.get("answer", "").strip().upper()
            correct_answer = str(question.answer or "").strip().upper()
            is_correct = (student_answer == correct_answer)

            if is_correct:
                correct_count += 1

            # 保存答题记录
            answer_record = StudentAnswer(
                answer_id=f"ans_{request.student_id}_{request.practice_id}_{question.question_id}",
                student_id=request.student_id,
                question_id=question.question_id,
                exam_record_id=request.practice_id,
                student_answer=student_answer,
                is_correct=is_correct,
            )
            db.add(answer_record)

        # 更新学生练习完成数
        if student:
            student.exercises_completed += 1
            student.last_exercise_at = datetime.utcnow()

        db.commit()

        # Trigger LLM barrier diagnosis in background for this exam
        import threading, asyncio as _asyncio
        def _run_diagnosis_bg():
            try:
                from app.models.database import get_db as _get_db
                _bg_db = next(_get_db())
                from app.api.diagnosis import run_llm_barrier_diagnosis
                loop = _asyncio.new_event_loop()
                _asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    run_llm_barrier_diagnosis(exam_record_id=request.practice_id, db=_bg_db)
                )
                _bg_db.close()
                loop.close()
            except Exception as _e:
                print(f"[Practice] Background diagnosis failed: {_e}", flush=True)
        threading.Thread(target=_run_diagnosis_bg, daemon=True).start()

        # 更新 barrier_type（基于最近答题正确率）
        try:
            all_recent = db.query(StudentAnswer).filter(
                StudentAnswer.student_id == request.student_id,
            ).order_by(StudentAnswer.answered_at.desc()).limit(20).all()

            correct = sum(1 for a in all_recent if a.is_correct)
            total = len(all_recent)
            if all_recent and total > 0:
                rate = correct / total
                if rate < 0.4:
                    dominant = "concept"  # 正确率很低 → 概念障碍
                elif rate < 0.7:
                    dominant = "reading"
                else:
                    dominant = "expression"
                student.barrier_type = {
                    k: (0.7 if k == dominant else 0.15)
                    for k in ("concept", "reading", "expression")
                }
                student.barrier_last_updated = datetime.utcnow()
                db.commit()
        except Exception:
            pass  # barrier 更新非关键路径

        accuracy = correct_count / total_count if total_count > 0 else 0

        # Check if this exam is fully completed by the class
        exam_completed = False
        try:
            exam = db.query(ExamRecord).filter(ExamRecord.record_id == request.practice_id).first()
            if exam:
                students = db.query(Student).filter(Student.class_id == exam.class_id).count()
                submitted = db.query(StudentAnswer.exam_record_id, StudentAnswer.student_id).filter(
                    StudentAnswer.exam_record_id == request.practice_id
                ).distinct().count()
                exam_completed = submitted >= students
        except Exception:
            pass

        return PracticeResult(
            practice_id=request.practice_id,
            student_id=request.student_id,
            correct_count=correct_count,
            total_count=total_count,
            accuracy=round(accuracy, 2),
            difficulty_appropriate=0.4 <= accuracy <= 0.8,
            barrier_change={"concept": 0.3, "reading": 0.4, "expression": 0.3}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.get("/effect/{student_id}")
async def get_practice_effect(student_id: str, db: Session = Depends(get_db)):
    """
    查看自适应练习效果
    """
    # 查询学生历史练习
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的练习记录
    practices = db.query(ExamRecord).filter(
        ExamRecord.class_id == student.class_id,
        ExamRecord.type == RecordType.PRACTICE
    ).order_by(ExamRecord.exam_date).all()

    if len(practices) < 2:
        return {
            "student_id": student_id,
            "message": "练习数据不足，无法评估效果"
        }

    # 计算最近两次练习的正确率对比
    latest = practices[-1]
    previous = practices[-2]

    latest_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == latest.record_id,
        StudentAnswer.student_id == student_id
    ).all()

    previous_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == previous.record_id,
        StudentAnswer.student_id == student_id
    ).all()

    latest_correct = sum(1 for a in latest_answers if a.is_correct)
    previous_correct = sum(1 for a in previous_answers if a.is_correct)

    latest_accuracy = latest_correct / len(latest_answers) if latest_answers else 0
    previous_accuracy = previous_correct / len(previous_answers) if previous_answers else 0

    improvement = latest_accuracy - previous_accuracy

    return {
        "student_id": student_id,
        "student_name": student.name,
        "improvement": {
            "before_practice_date": previous.exam_date.strftime("%Y-%m-%d") if previous.exam_date else None,
            "before_accuracy": round(previous_accuracy, 2),
            "after_practice_date": latest.exam_date.strftime("%Y-%m-%d") if latest.exam_date else None,
            "after_accuracy": round(latest_accuracy, 2),
            "improvement_rate": round(improvement, 2) if improvement != 0 else 0
        }
    }


@router.post("/push/daily")
async def push_daily_practice(db: Session = Depends(get_db)):
    """
    手动触发每日练习推送（供教师操作）
    """
    from app.scheduler.daily_practice import daily_practice_job
    from app.services.notification_service import send_practice_notification

    # 获取所有学生
    students = db.query(Student).filter(Student.status == "approved").all()

    pushed_students = 0
    pushed_parents = 0

    for student in students:
        # 获取今日练习
        from datetime import datetime
        today = datetime.utcnow().date()

        practice = db.query(ExamRecord).filter(
            ExamRecord.class_id == student.class_id,
            ExamRecord.type == RecordType.PRACTICE,
            ExamRecord.exam_date >= datetime.combine(today, datetime.min.time())
        ).first()

        if practice:
            # 更新学生最后练习时间
            student.last_exercise_at = datetime.utcnow()
            pushed_students += 1

            # 发送通知给家长
            sent = send_practice_notification(student.student_id, practice.name)
            pushed_parents += sent

    db.commit()

    return {
        "success": True,
        "message": f"已推送 {pushed_students} 名学生的练习任务，发送 {pushed_parents} 条家长通知"
    }


# ============================================================
# P5-3: 练习模块补充端点
# ============================================================


@router.get("/{practice_id}/questions")
async def get_practice_questions(practice_id: str, db: Session = Depends(get_db)):
    """获取指定练习的题目列表"""
    practice = db.query(ExamRecord).filter(ExamRecord.record_id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail=f"练习记录 {practice_id} 不存在")

    questions = db.query(Question).filter(Question.record_id == practice_id).all()

    return {
        "success": True,
        "practice_id": practice_id,
        "practice_name": practice.name,
        "total_questions": len(questions),
        "questions": [
            {
                "question_id": q.question_id,
                "content": q.content,
                "options": q.options,
                "answer": q.answer,
                "analysis": q.analysis,
                "knowledge_points": q.knowledge_points,
                "difficulty": q.difficulty.value if hasattr(q.difficulty, 'value') else q.difficulty
            }
            for q in questions
        ]
    }


@router.get("/history/{student_id}")
async def get_practice_history(
    student_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取学生练习历史"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的练习记录
    practices = db.query(ExamRecord).filter(
        ExamRecord.type == RecordType.PRACTICE
    ).order_by(ExamRecord.exam_date.desc()).limit(limit).all()

    history = []
    for p in practices:
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == p.record_id,
            StudentAnswer.student_id == student_id
        ).all()

        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)

        history.append({
            "practice_id": p.record_id,
            "name": p.name,
            "date": p.exam_date.strftime("%Y-%m-%d %H:%M") if p.exam_date else None,
            "total_questions": total,
            "correct_count": correct,
            "accuracy": round(correct / total, 2) if total > 0 else 0,
            "status": "completed" if total > 0 else "pending"
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "history": history
    }


# ── wrong/list, wrong/master, review/list, historical 已迁至 practice_wrong.py ──
