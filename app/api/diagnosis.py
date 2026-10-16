"""
F4: 学生障碍类型AI诊断 API
基于PRD v1.0完整版功能规格
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import json
from sqlalchemy.orm import Session

from app.models.database import (
    Student, ExamRecord, StudentAnswer, Question, BarrierConfig, Class,
    get_db, BarrierType, Parent, StudentParentBinding, ParentNotification,
    OperationLog
)

router = APIRouter()


class StudentDiagnosis(BaseModel):
    """学生障碍诊断结果"""
    student_id: str
    student_name: str
    barrier_type: Dict[str, float]  # {concept: 0.3, reading: 0.5, expression: 0.2}
    dominant_barrier: str  # 主要障碍类型
    weak_knowledge_points: List[str]  # 薄弱知识点
    recommended_intervention: str  # 推荐干预策略
    last_updated: str


class BarrierDiagnosisResponse(BaseModel):
    """障碍诊断响应"""
    class_id: str
    exam_record_id: str
    students: List[StudentDiagnosis]
    class_barrier_distribution: Dict[str, int]  # {concept: 25, reading: 40, expression: 25}
    avg_mastery: float


class BarrierConfigRequest(BaseModel):
    """障碍诊断配置请求"""
    concept_threshold: int = 3  # 1-5
    reading_threshold: int = 2  # 1-5
    expression_threshold: int = 3  # 1-5
    mastery_threshold: int = 3  # 1-5
    auto_sync_to_student: bool = False


class LearningPlanRequest(BaseModel):
    """生成学习计划请求"""
    student_id: str
    barrier_type: str  # concept/reading/expression
    weak_knowledge_points: List[str]
    recent_performance: Optional[Dict] = None  # 可选的近期表现数据


class LearningPlanResponse(BaseModel):
    """学习计划响应"""
    student_id: str
    student_name: str
    plan: Dict  # LLM生成的学习计划
    generated_at: str


class BarrierConfigResponse(BaseModel):
    """障碍诊断配置响应"""
    teacher_id: str
    concept_threshold: int
    reading_threshold: int
    expression_threshold: int
    mastery_threshold: int
    auto_sync_to_student: bool


class OverrideDiagnosisRequest(BaseModel):
    """老师推翻诊断请求"""
    barrier_type: str  # concept/reading/expression
    reason: Optional[str] = None


class RunLLMDiagnosisResponse(BaseModel):
    """LLM 诊断执行结果"""
    exam_id: str
    analyzed_count: int
    failed_count: int
    barrier_distribution: Dict[str, int]


# 干预建议
_INTERVENTIONS = {
    BarrierType.CONCEPT.value: "建议加强基础概念复习，使用思维导图梳理知识体系，重点理解\"为什么\"而非死记硬背",
    BarrierType.READING.value: "建议练习审题技巧，使用划线法提取题目关键信息，注意题目中的限定词和隐含条件",
    BarrierType.EXPRESSION.value: "建议加强规范化表述训练，参考标准答案的表述方式，练习用专业化学用语回答"
}


@router.get("/barrier/{class_id}/{exam_record_id}", response_model=BarrierDiagnosisResponse)
async def diagnose_barrier_types(
    class_id: str,
    exam_record_id: str,
    db: Session = Depends(get_db)
):
    """
    班级学生障碍类型诊断
    输入: 班级ID + 考试记录ID
    输出: 每个学生的障碍类型占比 + 班级分布

    诊断规则（基于PRD F4）：
    - 概念理解型(concept): 错题集中在基础概念题，审题类题目正确率高
    - 审题障碍型(reading): 错题集中在长题干题目，概念类题目正确率高
    - 表述障碍型(expression): 错题集中在填空题/计算题，选择题正确率高
    """
    # 验证考试记录存在
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id,
        ExamRecord.class_id == class_id
    ).first()

    if not exam_record:
        raise HTTPException(status_code=404, detail=f"考试记录不存在")

    # 查询班级所有学生
    students = db.query(Student).filter(Student.class_id == class_id).all()

    if not students:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 没有学生")

    diagnoses = []
    total_barriers = {"concept": 0, "reading": 0, "expression": 0}
    total_mastery = 0.0

    for student in students:
        # 查询该学生的答题记录
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student.student_id,
            StudentAnswer.exam_record_id == exam_record_id
        ).all()

        # 统计各类型错误
        errors_by_type = {"concept": 0, "reading": 0, "expression": 0}
        weak_kps = []
        kp_error_count: Dict[str, int] = {}

        for ans in answers:
            if ans.is_correct:
                continue

            # 获取题目信息
            question = db.query(Question).filter(
                Question.question_id == ans.question_id
            ).first()

            if not question:
                continue

            # 根据题目类型判断障碍
            barrier = ans.barrier_type
            if barrier:
                errors_by_type[barrier.value] += 1

            # 统计知识点错误
            for kp in (question.knowledge_points or []):
                kp_error_count[kp] = kp_error_count.get(kp, 0) + 1

        # 找出薄弱知识点（错误最多的）
        sorted_kps = sorted(kp_error_count.items(), key=lambda x: x[1], reverse=True)
        weak_kps = [kp for kp, _ in sorted_kps[:3]]

        # 计算障碍类型占比
        total_errors = sum(errors_by_type.values())
        if total_errors == 0:
            # 无该考试数据 → 用学生表已有的累计障碍数据
            stored_bt = student.barrier_type
            if isinstance(stored_bt, str):
                try: stored_bt = json.loads(stored_bt)
                except: stored_bt = None
            if stored_bt and isinstance(stored_bt, dict) and sum(stored_bt.values()) > 0:
                barrier_type = {k: round(v, 2) for k, v in stored_bt.items()}
            else:
                barrier_type = {"concept": 0.33, "reading": 0.33, "expression": 0.34}
        else:
            barrier_type = {
                k: round(v / total_errors, 2)
                for k, v in errors_by_type.items()
            }

        # 确定主要障碍
        dominant = max(barrier_type, key=barrier_type.get)

        diagnoses.append(StudentDiagnosis(
            student_id=student.student_id,
            student_name=student.name,
            barrier_type=barrier_type,
            dominant_barrier=dominant,
            weak_knowledge_points=weak_kps,
            recommended_intervention=_INTERVENTIONS.get(dominant, ""),
            last_updated=datetime.now().strftime("%Y-%m-%d")
        ))

        total_barriers[dominant] += 1

        # 计算掌握度（简化版：答对题数/总题数）
        correct_count = len([a for a in answers if a.is_correct])
        mastery = correct_count / len(answers) if answers else 0
        total_mastery += mastery

    avg_mastery = total_mastery / len(students) if students else 0

    return BarrierDiagnosisResponse(
        class_id=class_id,
        exam_record_id=exam_record_id,
        students=diagnoses,
        class_barrier_distribution=total_barriers,
        avg_mastery=round(avg_mastery, 2)
    )


@router.post("/run-llm/{exam_record_id}", response_model=RunLLMDiagnosisResponse)
async def run_llm_barrier_diagnosis(
    exam_record_id: str,
    db: Session = Depends(get_db)
):
    """
    F4: 对一场考试的错误答案运行 LLM 障碍诊断
    对错误率>30%的题目，调用 LLM 分析学生障碍类型，
    结果写入 StudentAnswer.barrier_type 并聚合到 Student.barrier_type
    """
    exam_record = db.query(ExamRecord).filter(
        ExamRecord.record_id == exam_record_id
    ).first()
    if not exam_record:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    # 查找所有错误答案（无 barrier_type 的优先）
    wrong_answers = db.query(StudentAnswer).filter(
        StudentAnswer.exam_record_id == exam_record_id,
        StudentAnswer.is_correct == False,
    ).order_by(
        StudentAnswer.barrier_type.is_(None).desc()  # 未诊断的优先
    ).limit(10).all()  # 最多分析10个

    if not wrong_answers:
        return RunLLMDiagnosisResponse(
            exam_id=exam_record_id,
            analyzed_count=0, failed_count=0,
            barrier_distribution={"concept": 0, "reading": 0, "expression": 0}
        )

    from app.services.llm_service import llm_service
    import concurrent.futures

    analyzed, failed = 0, 0
    barrier_dist = {"concept": 0, "reading": 0, "expression": 0}

    # 收集所有需要更新的 student_id
    updated_students = set()

    def diagnose_single(ans):
        nonlocal analyzed, failed
        question = db.query(Question).filter(
            Question.question_id == ans.question_id
        ).first()
        if not question:
            return

        q_content = question.content or ""
        correct = question.answer or ""
        student_ans = ans.student_answer or ""

        result = llm_service.diagnose_barrier_type(
            student_error_history=[{
                "question": q_content[:300],
                "wrong_answer": student_ans,
                "correct_answer": correct,
            }],
            question_content=q_content[:500],
            student_answer=student_ans,
            correct_answer=correct,
        )

        if result.get("success"):
            content = result.get("content", "{}")
            import re as _re
            import json as _json
            _json_match = _re.search(r'\{[\s\S]*\}', content)
            if _json_match:
                try:
                    data = _json.loads(_json_match.group())
                    bt = data.get("barrier_type", "concept")
                    if bt in ("concept", "reading", "expression"):
                        ans.barrier_type = getattr(BarrierType, bt.upper(), BarrierType.CONCEPT)
                        analyzed += 1
                except _json.JSONDecodeError:
                    failed += 1
            else:
                failed += 1
        else:
            failed += 1

    # 并发最多5个
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(lambda a: diagnose_single(a), wrong_answers))

    db.commit()

    # 聚合更新 Student.barrier_type
    for ans in wrong_answers:
        if ans.barrier_type and ans.student_id:
            updated_students.add(ans.student_id)
            bt = ans.barrier_type.value
            barrier_dist[bt] = barrier_dist.get(bt, 0) + 1

    for sid in updated_students:
        student = db.query(Student).filter(Student.student_id == sid).first()
        if student:
            all_answers = db.query(StudentAnswer).filter(
                StudentAnswer.student_id == sid,
                StudentAnswer.is_correct == False,
                StudentAnswer.barrier_type.isnot(None),
            ).all()
            counts = {"concept": 0, "reading": 0, "expression": 0}
            for a in all_answers:
                if a.barrier_type:
                    counts[a.barrier_type.value] = counts.get(a.barrier_type.value, 0) + 1
            total = sum(counts.values()) or 1
            student.barrier_type = {k: round(v / total, 2) for k, v in counts.items()}
            # 补充缺失的类型
            for bt in ("concept", "reading", "expression"):
                if bt not in student.barrier_type:
                    student.barrier_type[bt] = 0.0
            student.barrier_last_updated = datetime.utcnow()

    db.commit()

    return RunLLMDiagnosisResponse(
        exam_id=exam_record_id,
        analyzed_count=analyzed,
        failed_count=failed,
        barrier_distribution=barrier_dist,
    )


@router.put("/override/{student_id}")
async def override_barrier_diagnosis(
    student_id: str,
    request: OverrideDiagnosisRequest,
    db: Session = Depends(get_db)
):
    """
    F4: 老师推翻 AI 诊断结论
    手动指定学生的障碍类型，系统记录操作日志
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    bt = request.barrier_type
    if bt not in ("concept", "reading", "expression"):
        raise HTTPException(status_code=400, detail="障碍类型必须是 concept/reading/expression")

    # 保存旧值
    old_barrier = dict(student.barrier_type or {})

    # 更新为手动指定的类型（权重90%给指定类型）
    new_barrier = {"concept": 0.05, "reading": 0.05, "expression": 0.05}
    new_barrier[bt] = 0.90
    student.barrier_type = new_barrier
    student.barrier_last_updated = datetime.utcnow()

    # 记录操作日志
    log = OperationLog(
        user_id=student_id,
        action="override_diagnosis",
        target_type="student",
        target_id=student_id,
        detail={
            "old_barrier": old_barrier,
            "new_barrier": new_barrier,
            "reason": request.reason,
            "changed_by": "teacher",
        },
    )
    db.add(log)
    db.commit()

    return {
        "success": True,
        "message": f"诊断已更新为 {bt}",
        "student_id": student_id,
        "old_barrier": old_barrier,
        "new_barrier": new_barrier,
    }


@router.get("/barrier/{student_id}")
async def get_student_barrier(student_id: str, db: Session = Depends(get_db)):
    """
    获取单个学生障碍类型详情
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 获取最新的障碍类型
    barrier_type = student.barrier_type or {"concept": 0.33, "reading": 0.33, "expression": 0.34}
    dominant = max(barrier_type, key=barrier_type.get)

    # TODO: 计算真正的薄弱知识点（基于历史答题数据）
    weak_kps = ["盐类水解", "电解池"]  # 简化版

    return StudentDiagnosis(
        student_id=student_id,
        student_name=student.name,
        barrier_type=barrier_type,
        dominant_barrier=dominant,
        weak_knowledge_points=weak_kps,
        recommended_intervention=_INTERVENTIONS.get(dominant, ""),
        last_updated=student.barrier_last_updated.strftime("%Y-%m-%d") if student.barrier_last_updated else datetime.now().strftime("%Y-%m-%d")
    )


@router.put("/config/{teacher_id}", response_model=BarrierConfigResponse)
async def update_barrier_config(
    teacher_id: str,
    config: BarrierConfigRequest,
    db: Session = Depends(get_db)
):
    """
    更新障碍诊断规则配置
    老师可调整各障碍类型的触发阈值
    """
    # 查询是否已存在配置
    existing = db.query(BarrierConfig).filter(
        BarrierConfig.teacher_id == teacher_id
    ).first()

    if existing:
        # 更新现有配置
        existing.concept_threshold = config.concept_threshold
        existing.reading_threshold = config.reading_threshold
        existing.expression_threshold = config.expression_threshold
        existing.mastery_threshold = config.mastery_threshold
        existing.auto_sync_to_student = config.auto_sync_to_student
        existing.updated_at = datetime.utcnow()
    else:
        # 创建新配置
        import uuid
        new_config = BarrierConfig(
            config_id=str(uuid.uuid4()),
            teacher_id=teacher_id,
            concept_threshold=config.concept_threshold,
            reading_threshold=config.reading_threshold,
            expression_threshold=config.expression_threshold,
            mastery_threshold=config.mastery_threshold,
            auto_sync_to_student=config.auto_sync_to_student
        )
        db.add(new_config)

    db.commit()

    return BarrierConfigResponse(
        teacher_id=teacher_id,
        concept_threshold=config.concept_threshold,
        reading_threshold=config.reading_threshold,
        expression_threshold=config.expression_threshold,
        mastery_threshold=config.mastery_threshold,
        auto_sync_to_student=config.auto_sync_to_student
    )


@router.get("/config/{teacher_id}", response_model=BarrierConfigResponse)
async def get_barrier_config(teacher_id: str, db: Session = Depends(get_db)):
    """
    获取障碍诊断规则配置
    """
    config = db.query(BarrierConfig).filter(
        BarrierConfig.teacher_id == teacher_id
    ).first()

    if config:
        return BarrierConfigResponse(
            teacher_id=teacher_id,
            concept_threshold=config.concept_threshold,
            reading_threshold=config.reading_threshold,
            expression_threshold=config.expression_threshold,
            mastery_threshold=config.mastery_threshold,
            auto_sync_to_student=config.auto_sync_to_student
        )

    # 返回默认值
    return BarrierConfigResponse(
        teacher_id=teacher_id,
        concept_threshold=3,
        reading_threshold=2,
        expression_threshold=3,
        mastery_threshold=3,
        auto_sync_to_student=False
    )


@router.post("/learning-plan/generate", response_model=LearningPlanResponse)
async def generate_student_learning_plan(
    request: LearningPlanRequest,
    db: Session = Depends(get_db)
):
    """
    生成学生个性化学习计划
    基于学生障碍类型和薄弱知识点,使用LLM生成定制化学习路径
    """
    # 查询学生信息
    student = db.query(Student).filter(Student.student_id == request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {request.student_id} 不存在")

    # 调用LLM服务生成学习计划
    from app.services.llm_service import llm_service

    result = llm_service.generate_learning_plan(
        student_name=student.name,
        barrier_type=request.barrier_type,
        weak_knowledge_points=request.weak_knowledge_points,
        recent_performance=request.recent_performance
    )

    if not result.get("success") or not result.get("content", "").strip():
        raise HTTPException(status_code=500, detail=f"学习计划生成失败: LLM返回为空，请重试")

    # llm_service.generate_learning_plan 已通过Markdown解析器返回结构化JSON
    plan_content = result.get("content", "{}")
    plan_data = json.loads(plan_content)

    if not plan_data.get("plan_title"):
        raise HTTPException(status_code=500, detail="LLM返回的计划内容不完整，请重试")

    return LearningPlanResponse(
        student_id=request.student_id,
        student_name=student.name,
        plan=plan_data,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M")
    )


@router.post("/learning-plan/apply/{student_id}")
async def apply_student_learning_plan(
    student_id: str,
    plan_data: Dict,
    db: Session = Depends(get_db)
):
    """
    应用学习计划到学生
    将生成的学习计划保存到 SqliteStore 长期记忆，学生端即刻可见
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 直接写 students 表
    student.current_plan = plan_data
    db.commit()

    # 写入历史记录
    try:
        from app.models.database import LearningPlanHistory
        db.add(LearningPlanHistory(
            student_id=student_id,
            plan_title=plan_data.get("plan_title", "学习计划"),
            plan_data=plan_data,
        ))
        db.commit()
    except Exception:
        pass

    # 更新内存缓存
    import time as _t
    _plan_cache[student_id] = {"plan": plan_data, "expires_at": _t.time() + 86400}

    return {
        "success": True,
        "message": f"学习计划已保存，{student.name} 可在学生端查看",
        "student_id": student_id,
        "student_name": student.name,
    }


@router.get("/learning-plan/{student_id}/history")
async def get_plan_history(student_id: str, db: Session = Depends(get_db)):
    """获取学生学习计划历史"""
    from app.models.database import LearningPlanHistory
    records = db.query(LearningPlanHistory).filter(
        LearningPlanHistory.student_id == student_id
    ).order_by(LearningPlanHistory.created_at.desc()).limit(20).all()
    return {
        "success": True,
        "history": [{
            "id": r.id,
            "plan_title": r.plan_title,
            "plan_data": r.plan_data,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
        } for r in records]
    }


@router.post("/learning-plan/send-to-parent/{student_id}")
async def send_plan_to_parent(
    student_id: str,
    plan_data: Optional[Dict] = None,
    db: Session = Depends(get_db)
):
    """
    发送学生学习计划给家长
    推送至家长端App查看
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生的所有绑定家长
    bindings = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.status == "active"
    ).all()

    if not bindings:
        return {
            "success": False,
            "message": "该学生未绑定家长，无法发送",
            "student_id": student_id
        }

    sent_count = 0
    for binding in bindings:
        # 创建通知记录
        notification = ParentNotification(
            notification_id=f"notif_{student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
            parent_id=binding.parent_id,
            student_id=student_id,
            type="learning_plan",
            title=f"📖 {student.name} 的个性化学习计划已生成",
            content=f"主要障碍类型: {student.barrier_type.get('dominant', '概念理解型') if isinstance(student.barrier_type, dict) else '概念理解型'}" if plan_data is None else str(plan_data),
            is_read=False,
            sent_at=datetime.utcnow()
        )
        db.add(notification)
        sent_count += 1

    db.commit()

    return {
        "success": True,
        "message": f"学习计划已发送给 {sent_count} 位家长",
        "student_id": student_id,
        "sent_count": sent_count
    }


# In-memory plan cache with TTL (24h)
import time as _time
_plan_cache = {}  # student_id → {"plan": ..., "expires_at": ...}

@router.get("/learning-plan/{student_id}")
async def get_student_learning_plan(
    student_id: str,
    db: Session = Depends(get_db)
):
    """获取学生当前学习计划。有缓存返回缓存，无则调 LLM 生成。"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    now = _time.time()
    cached = _plan_cache.get(student_id)
    if cached and cached.get("expires_at", 0) > now:
        return {"success": True, "data": {"student_id": student_id, "student_name": student.name, "plan": cached["plan"]}}

    # Check students.current_plan (persisted by POST /apply)
    if student.current_plan and isinstance(student.current_plan, dict) and student.current_plan.get("plan_title"):
        _plan_cache[student_id] = {"plan": student.current_plan, "expires_at": now + 86400}
        return {"success": True, "data": {"student_id": student_id, "student_name": student.name, "plan": student.current_plan}}

    # Build barrier info from student data
    barrier = student.barrier_type or {}
    if isinstance(barrier, str):
        import json as _j; barrier = _j.loads(barrier)
    dominant = max(barrier.items(), key=lambda x: x[1]) if barrier else ("concept", 1.0)

    # Get weak knowledge points from recent wrong answers
    weak_kps = []
    try:
        from app.models.database import StudentAnswer, Question
        from collections import Counter
        wrong_answers = db.query(StudentAnswer).filter(
            StudentAnswer.student_id == student_id, StudentAnswer.is_correct == False
        ).order_by(StudentAnswer.answered_at.desc()).limit(30).all()
        kp_counter = Counter()
        for wa in wrong_answers:
            q = db.query(Question).filter(Question.question_id == wa.question_id).first()
            if q and q.knowledge_points:
                for kp in q.knowledge_points:
                    kp_counter[kp] += 1
        weak_kps = [kp for kp, _ in kp_counter.most_common(5)]
    except Exception:
        pass

    # Generate via LLM
    from app.services.llm_service import llm_service
    result = llm_service.generate_learning_plan(
        student_name=student.name,
        barrier_type=dominant[0],
        weak_knowledge_points=weak_kps or ["化学基础"],
        recent_performance={"exercises_completed": student.exercises_completed or 0},
    )

    plan_data = {}
    if result.get("success"):
        content = result.get("content", "{}")
        import re as _re, json as _j
        m = _re.search(r'\{[\s\S]*\}', content)
        if m:
            try:
                plan_data = _j.loads(m.group())
            except _j.JSONDecodeError:
                plan_data = {"plan_title": "AI 生成计划", "content": content[:500]}
    if not plan_data:
        plan_data = {
            "plan_title": f"{dominant[0]} 专项提升计划",
            "plan_period": "1周",
            "weak_kps": weak_kps,
            "dominant_barrier": dominant[0],
        }

    _plan_cache[student_id] = {"plan": plan_data, "expires_at": now + 86400}
    return {"success": True, "data": {"student_id": student_id, "student_name": student.name, "plan": plan_data}}


# ============================================================
# P5-1: 诊断模块补充端点
# ============================================================


@router.get("/plan/{student_id}")
async def get_student_diagnosis_plan(student_id: str, db: Session = Depends(get_db)):
    """
    获取学生已有的诊断学习计划
    由ChemAI Agent生成后存储，本端点仅做检索
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    barrier_type = student.barrier_type or {"concept": 0.33, "reading": 0.33, "expression": 0.34}
    dominant = max(barrier_type, key=barrier_type.get)

    # 查询该学生最近的答题记录，找出薄弱知识点
    recent_answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id == student_id,
        StudentAnswer.is_correct == False
    ).order_by(StudentAnswer.answered_at.desc()).limit(20).all()

    kp_error_count = {}
    for ans in recent_answers:
        question = db.query(Question).filter(Question.question_id == ans.question_id).first()
        if question:
            for kp in (question.knowledge_points or []):
                kp_error_count[kp] = kp_error_count.get(kp, 0) + 1

    sorted_kps = sorted(kp_error_count.items(), key=lambda x: x[1], reverse=True)
    weak_kps = [kp for kp, _ in sorted_kps[:5]]

    # 答题统计
    total_answers = db.query(StudentAnswer).filter(StudentAnswer.student_id == student_id).count()
    correct_answers = db.query(StudentAnswer).filter(StudentAnswer.student_id == student_id, StudentAnswer.is_correct == True).count()
    accuracy = round(correct_answers / total_answers, 2) if total_answers > 0 else 0

    # 确保有绑定码
    bind_code = getattr(student, 'bind_code', None)
    if not bind_code:
        import random
        bind_code = str(random.randint(100000, 999999))
        student.bind_code = bind_code
        db.commit()

    return {
        "success": True,
        "data": {
            "student_id": student_id,
            "student_name": student.name,
            "barrier_type": barrier_type,
            "dominant_barrier": dominant,
            "weak_knowledge_points": weak_kps,
            "total_answers": total_answers,
            "accuracy": accuracy,
            "bind_code": bind_code,
            "recommended_intervention": _INTERVENTIONS.get(dominant, ""),
            "last_updated": student.barrier_last_updated.strftime("%Y-%m-%d") if getattr(student, 'barrier_last_updated', None) else datetime.now().strftime("%Y-%m-%d")
        }
    }


class FeedbackRequest(BaseModel):
    """诊断反馈请求"""
    rating: Optional[int] = None  # 1-5 评分
    comment: Optional[str] = None  # 反馈内容
    accurate: Optional[bool] = None  # 诊断是否准确


@router.post("/{diagnosis_id}/feedback")
async def submit_diagnosis_feedback(
    diagnosis_id: str,
    feedback: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    提交诊断结果反馈
    学生对诊断结果的准确性进行评价
    """
    # feedback记录到操作日志
    from app.models.database import OperationLog
    log = OperationLog(
        user_id=diagnosis_id,
        action="feedback",
        target_type="diagnosis",
        target_id=diagnosis_id,
        detail={
            "rating": feedback.rating,
            "comment": feedback.comment,
            "accurate": feedback.accurate
        }
    )
    db.add(log)
    db.commit()

    return {
        "success": True,
        "message": "反馈提交成功"
    }


@router.get("/history/{student_id}")
async def get_diagnosis_history(
    student_id: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    获取学生历史诊断记录列表
    按考试分组统计每次的障碍分布
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")

    # 查询该学生参与过的所有考试/练习
    exam_records = db.query(ExamRecord).join(
        StudentAnswer, ExamRecord.record_id == StudentAnswer.exam_record_id
    ).filter(
        StudentAnswer.student_id == student_id
    ).order_by(ExamRecord.exam_date.desc()).limit(limit).all()

    history = []
    for exam in exam_records:
        # 统计本次考试的barrier分布
        answers = db.query(StudentAnswer).filter(
            StudentAnswer.exam_record_id == exam.record_id,
            StudentAnswer.student_id == student_id
        ).all()

        barrier_count = {"concept": 0, "reading": 0, "expression": 0}
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)

        for a in answers:
            if a.barrier_type and not a.is_correct:
                barrier_count[a.barrier_type.value] = barrier_count.get(a.barrier_type.value, 0) + 1

        history.append({
            "exam_record_id": exam.record_id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.strftime("%Y-%m-%d") if exam.exam_date else None,
            "accuracy": round(correct / total, 2) if total > 0 else 0,
            "barrier_distribution": barrier_count
        })

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student.name,
        "history": history
    }


@router.get("/class/{class_id}/stats")
async def get_class_barrier_stats(class_id: str, db: Session = Depends(get_db)):
    """
    班级障碍类型分布统计
    聚合全班学生的barrier_type字段
    """
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    students = db.query(Student).filter(Student.class_id == class_id).all()

    concept_count = 0
    reading_count = 0
    expression_count = 0
    student_count = len(students)

    for s in students:
        bt = s.barrier_type
        if bt and isinstance(bt, dict):
            dominant = max(bt, key=bt.get)
            if dominant == "concept":
                concept_count += 1
            elif dominant == "reading":
                reading_count += 1
            elif dominant == "expression":
                expression_count += 1

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "total_students": student_count,
        "distribution": {
            "concept": {"count": concept_count, "percentage": round(concept_count / student_count * 100, 1) if student_count > 0 else 0},
            "reading": {"count": reading_count, "percentage": round(reading_count / student_count * 100, 1) if student_count > 0 else 0},
            "expression": {"count": expression_count, "percentage": round(expression_count / student_count * 100, 1) if student_count > 0 else 0}
        }
    }


@router.get("/class/{class_id}/kp/{kp}")
async def get_kp_barrier_analysis(
    class_id: str,
    kp: str,
    db: Session = Depends(get_db)
):
    """
    按知识点的班级障碍分析
    查询指定知识点下学生的错误率和障碍分布
    """
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail=f"班级 {class_id} 不存在")

    # 查询该班级学生在指定知识点上的答题情况
    students = db.query(Student).filter(Student.class_id == class_id).all()
    student_ids = [s.student_id for s in students]

    # 查找包含该知识点的题目
    questions = db.query(Question).filter(
        Question.knowledge_points.contains(kp)
    ).all()
    question_ids = [q.question_id for q in questions]

    if not question_ids:
        return {
            "success": True,
            "class_id": class_id,
            "knowledge_point": kp,
            "total_questions": 0,
            "total_answers": 0,
            "error_rate": 0,
            "barrier_distribution": {"concept": 0, "reading": 0, "expression": 0},
            "message": "暂未找到该知识点的题目数据"
        }

    # 查询答题记录
    answers = db.query(StudentAnswer).filter(
        StudentAnswer.student_id.in_(student_ids),
        StudentAnswer.question_id.in_(question_ids)
    ).all()

    total = len(answers)
    errors = [a for a in answers if not a.is_correct]
    error_rate = len(errors) / total if total > 0 else 0

    barrier_dist = {"concept": 0, "reading": 0, "expression": 0}
    for a in errors:
        if a.barrier_type:
            bt = a.barrier_type.value
            barrier_dist[bt] = barrier_dist.get(bt, 0) + 1

    return {
        "success": True,
        "class_id": class_id,
        "class_name": class_obj.name,
        "knowledge_point": kp,
        "total_questions": len(questions),
        "total_answers": total,
        "error_count": len(errors),
        "error_rate": round(error_rate, 3),
        "barrier_distribution": barrier_dist
    }
