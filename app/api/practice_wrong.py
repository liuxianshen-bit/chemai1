"""错题本 & 复习管理 API
从 practice.py 拆分出来，独立管理错题和间隔复习功能。
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import Student, Question, StudentAnswer, get_db
from app.models.review_task import ReviewTask

router = APIRouter()


@router.get("/wrong/list")
async def get_wrong_questions_list(
    student_id: Optional[str] = None,
    limit: int = 50,
    knowledge_point: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取错题列表（全局，不限定考试）"""
    query = db.query(StudentAnswer).filter(StudentAnswer.is_correct == False)

    if student_id:
        query = query.filter(StudentAnswer.student_id == student_id)
    if knowledge_point:
        kp_questions = db.query(Question.question_id).filter(
            Question.knowledge_points.contains(knowledge_point)
        ).all()
        kp_ids = [q[0] for q in kp_questions]
        if kp_ids:
            query = query.filter(StudentAnswer.question_id.in_(kp_ids))

    wrong_answers = query.order_by(StudentAnswer.answered_at.desc()).limit(limit).all()

    seen_questions = set()
    unique_wrong = []
    for wa in wrong_answers:
        if wa.question_id not in seen_questions:
            seen_questions.add(wa.question_id)
            q = db.query(Question).filter(Question.question_id == wa.question_id).first()
            unique_wrong.append({
                "question_id": wa.question_id,
                "content": q.content if q else "",
                "options": q.options if q else None,
                "answer": q.answer if q else "",
                "analysis": q.analysis if q else "",
                "knowledge_points": q.knowledge_points if q else [],
                "difficulty": q.difficulty.value if q and hasattr(q.difficulty, 'value') else (q.difficulty if q else ""),
                "your_answer": wa.student_answer,
                "wrong_count": sum(1 for w in wrong_answers if w.question_id == wa.question_id),
                "last_error_at": wa.answered_at.strftime("%Y-%m-%d") if wa.answered_at else None
            })

    return {"success": True, "count": len(unique_wrong), "wrong_questions": unique_wrong}


@router.post("/wrong/{question_id}/master")
async def mark_wrong_question_mastered(
    question_id: str,
    student_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """标记错题已掌握"""
    question = db.query(Question).filter(Question.question_id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail=f"题目 {question_id} 不存在")

    if student_id:
        existing = db.query(ReviewTask).filter(
            ReviewTask.student_id == student_id,
            ReviewTask.question_id == question_id
        ).first()
        if existing:
            existing.status = "done"
            existing.completed_at = datetime.utcnow()
        else:
            review_task = ReviewTask(
                task_id=f"review_{student_id}_{question_id}",
                student_id=student_id,
                question_id=question_id,
                review_level=5,
                status="done",
                completed_at=datetime.utcnow()
            )
            db.add(review_task)
        db.commit()

    return {"success": True, "message": "题目已标记为已掌握", "question_id": question_id}


@router.get("/review/list")
async def get_review_question_list(
    student_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """获取待复习题目列表"""
    query = db.query(ReviewTask).filter(ReviewTask.status == "pending")
    if student_id:
        query = query.filter(ReviewTask.student_id == student_id)

    tasks = query.order_by(ReviewTask.next_review_at.asc()).limit(limit).all()

    review_list = []
    for t in tasks:
        q = db.query(Question).filter(Question.question_id == t.question_id).first()
        student = db.query(Student).filter(Student.student_id == t.student_id).first()
        review_list.append({
            "task_id": t.task_id, "student_id": t.student_id,
            "student_name": student.name if student else "",
            "question_id": t.question_id,
            "question_content": q.content if q else "",
            "knowledge_points": q.knowledge_points if q else [],
            "review_level": t.review_level,
            "next_review_at": t.next_review_at.strftime("%Y-%m-%d") if t.next_review_at else None,
            "consecutive_correct": t.consecutive_correct,
            "consecutive_errors": t.consecutive_errors
        })

    return {"success": True, "count": len(review_list), "review_list": review_list}


@router.get("/historical")
async def get_practice_historical_questions(
    source: Optional[str] = None,
    year: Optional[int] = None,
    knowledge_point: Optional[str] = None,
    difficulty: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 20
):
    """获取历史真题（练习场景）"""
    from app.services.exam_bank import exam_bank_service
    questions = exam_bank_service.search_questions(
        source=source, year=str(year) if year else None,
        knowledge_point=knowledge_point, difficulty=difficulty, keyword=keyword
    )
    result = questions[:limit]
    return {
        "success": True, "count": len(result),
        "questions": [
            {"exam_id": q.exam_id, "source": q.source, "year": q.year,
             "question_number": q.question_number, "content": q.content,
             "answer": q.answer, "analysis": q.analysis,
             "knowledge_points": q.knowledge_points, "difficulty": q.difficulty}
            for q in result
        ]
    }
