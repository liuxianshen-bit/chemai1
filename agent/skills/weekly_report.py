"""家长周报 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="weekly_report",
    description="生成学生本周化学学习周报，包含学习内容、掌握情况、成长空间和家庭配合建议。通俗易懂，面向家长。",
    parameters={"student_id": "学生ID，如 202610101"},
)
async def weekly_report(student_id: str = "") -> dict:
    """仅限家长 persona 使用。权限由 persona YAML available_skills + registry.execute() 两层过滤。"""
    import sys, os, json
    from dotenv import load_dotenv
    load_dotenv()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from app.models.database import get_db
    from sqlalchemy import text

    session = next(get_db())

    # 查学生基本信息
    student_row = session.execute(
        text("SELECT name, class_id, barrier_type, exercises_completed FROM students WHERE student_id = :sid"),
        {"sid": student_id},
    ).fetchone()

    if not student_row:
        session.close()
        return {"error": f"学生 {student_id} 不存在"}

    student_name = student_row[0]
    barrier = json.loads(student_row[2]) if isinstance(student_row[2], str) else student_row[2]

    # 查练习完成情况
    exam_count = session.execute(
        text("SELECT COUNT(*) FROM exam_records WHERE class_id = :cid"),
        {"cid": student_row[1]},
    ).fetchone()[0]

    session.close()

    # 调 LLM 生成报告
    from agent.provider.deepseek import DeepSeekProvider

    provider = registry._provider or DeepSeekProvider()

    system_prompt = """你是ChemAI家长助手。生成学生本周学习报告。

原则:
- 鼓励为主，先肯定进步
- 用通俗语言，不用教育学术语
- 给出家长可操作的建议
- 不制造焦虑"""

    prompt = f"""请为 {student_name} 生成本周化学学习报告:

学习数据:
- 本周参加了 {exam_count} 次课堂练习
- 学习特点: {json.dumps(barrier, ensure_ascii=False)}

请生成200字以内的报告，直接回复文本，不要JSON."""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=512,
    )

    await provider.close()

    return {
        "student_name": student_name,
        "report": result.content,
        "exam_count": exam_count,
    }
