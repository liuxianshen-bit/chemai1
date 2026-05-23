"""答疑辅导 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="chemistry_tutor",
    description="回答学生的化学问题，引导式教学（不直接给答案）。适用于概念解释、解题思路引导、知识点讲解。",
    parameters={
        "question": "学生的化学问题",
        "student_level": "学生水平（可选），如 基础薄弱/中等/较好",
    },
)
async def chemistry_tutor(question: str = "", student_level: str = "中等") -> dict:
    import os
    from dotenv import load_dotenv
    load_dotenv()

    from agent.provider.deepseek import DeepSeekProvider

    provider = DeepSeekProvider()

    system_prompt = f"""你是高中化学AI助教。学生水平: {student_level}。

教学原则:
1. 引导式教学: 不直接给答案，先问学生"你是怎么想的"
2. 分步讲解: 复杂问题拆成2-3步，每步确认理解
3. 联系考点: 提及高考中的常见题型
4. 鼓励为主: 对正确思路给予肯定
5. 单次回复不超过500字
6. 不确定时诚实说不知道"""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.7,
        max_tokens=1024,
    )

    await provider.close()
    return {"answer": result.content, "model": result.model}
