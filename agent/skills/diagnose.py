"""学生障碍诊断 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="diagnose_barrier",
    description="诊断学生的化学学习障碍类型（概念理解型/审题障碍型/表述障碍型），返回障碍分布、主导类型和教学干预建议。",
    parameters={
        "student_id": "学生ID，如 202610101",
        "class_id": "班级ID（可选），用于批量诊断",
    },
)
async def diagnose_barrier(
    student_id: str = "",
    class_id: str = "",
) -> dict:
    import sys, os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    if student_id:
        # 单个学生诊断
        row = session.execute(
            text(
                "SELECT name, barrier_type, exercises_completed FROM students WHERE student_id = :sid"
            ),
            {"sid": student_id},
        ).fetchone()

        session.close()
        if not row:
            return {"error": f"学生 {student_id} 不存在"}

        import json

        barrier = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        dominant = max(barrier.items(), key=lambda x: x[1]) if barrier else ("unknown", 0)

        return {
            "student_id": student_id,
            "student_name": row[0],
            "barrier_distribution": barrier,
            "dominant_barrier": dominant[0],
            "exercises_completed": row[2] or 0,
        }

    elif class_id:
        # 班级诊断
        rows = session.execute(
            text(
                "SELECT student_id, name, barrier_type FROM students WHERE class_id = :cid"
            ),
            {"cid": class_id},
        ).fetchall()
        session.close()

        import json

        students = []
        concept_count = reading_count = expression_count = 0
        for row in rows:
            barrier = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            if barrier:
                students.append(
                    {
                        "student_id": row[0],
                        "student_name": row[1],
                        "dominant": max(barrier.items(), key=lambda x: x[1])[0],
                    }
                )
                # 统计
                for bt, val in barrier.items():
                    if val >= 0.5:
                        if bt == "concept":
                            concept_count += 1
                        elif bt == "reading":
                            reading_count += 1
                        elif bt == "expression":
                            expression_count += 1

        return {
            "class_id": class_id,
            "total_students": len(students),
            "barrier_distribution": {
                "concept": concept_count,
                "reading": reading_count,
                "expression": expression_count,
            },
            "students": students[:10],  # 前10个
        }

    session.close()
    return {"error": "请提供 student_id 或 class_id"}
