"""自适应练习 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="assign_adaptive_practice",
    description="为班级学生布置自适应练习。根据每个学生的障碍类型和最近发展区生成个性化化学练习题。",
    parameters={
        "class_id": "班级ID",
        "knowledge_points": "知识点列表，逗号分隔",
        "question_count": "题目数量，默认5",
    },
)
async def assign_adaptive_practice(
    class_id: str = "",
    knowledge_points: str = "",
    question_count: str = "5",
) -> dict:
    import sys, os
    from dotenv import load_dotenv
    load_dotenv()
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    from app.api.practice import (
        _calculate_zpd_difficulty, _get_weak_kps, _get_dominant_barrier
    )
    from app.services.llm_service import llm_service
    from app.models.database import Student, Question, ExamRecord, StudentAnswer, get_db
    from app.models.database import Difficulty, AuditStatus, QuestionSource, RecordType
    from datetime import datetime
    from sqlalchemy.orm import Session

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]
    qty = int(question_count)

    db = next(get_db())
    try:
        students = db.query(Student).filter(Student.class_id == class_id).all()
        if not students:
            return {"error": f"班级 {class_id} 无学生"}

        assigned = []
        for student in students[:5]:
            zpd = _calculate_zpd_difficulty(student.student_id, db)
            barrier = _get_dominant_barrier(student.student_id, db)
            weak = _get_weak_kps(student.student_id, db)
            use_kps = weak if weak else kps

            result = llm_service.generate_questions(
                knowledge_points=use_kps, difficulty=zpd,
                quantity=qty, question_types=["choice"],
            )
            if result.get("success"):
                assigned.append({
                    "student_name": student.name,
                    "zpd_difficulty": zpd,
                    "barrier": barrier,
                    "question_count": qty,
                    "weak_kps": weak,
                })

        return {
            "assigned_count": len(assigned),
            "assigned": assigned,
        }
    finally:
        db.close()
