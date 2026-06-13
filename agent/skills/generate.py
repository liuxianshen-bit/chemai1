"""AI 出题 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="generate_questions",
    description="根据知识点和难度生成高中化学练习题。自动审核生成的化学方程式是否配平。返回题目列表和审核结果。",
    parameters={
        "knowledge_points": "知识点列表，逗号分隔，如 盐类水解,电离平衡",
        "difficulty": "难度 easy/medium/hard，默认 medium",
        "quantity": "题目数量，默认5",
    },
)
async def generate_questions(
    knowledge_points: str = "",
    difficulty: str = "medium",
    quantity: str = "5",
) -> dict:
    import os
    from dotenv import load_dotenv

    load_dotenv()

    from agent.provider.deepseek import DeepSeekProvider
    from app.services.chemical_balance import audit_chemical_equation
    import json, re

    kps = [k.strip() for k in knowledge_points.split(",") if k.strip()]
    qty = int(quantity)

    provider = registry._provider or DeepSeekProvider()

    system_prompt = """你是资深高中化学教师。根据知识点生成高质量的化学选择题。

要求:
1. 题目科学性100%正确，化学方程式必须配平
2. 4个选项，有区分度
3. 注明正确答案和解析
4. 适当设置陷阱选项

返回纯JSON（不要markdown代码块）:
{
  "questions": [
    {
      "content": "题目正文",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "answer": "A",
      "explanation": "解析",
      "knowledge_points": ["知识点1"],
      "difficulty": "medium",
      "has_equation": false
    }
  ]
}"""

    prompt = f"请生成{qty}道{difficulty}难度的高中化学题。知识点: {', '.join(kps) if kps else '高中化学综合'}"

    try:
        result = await provider.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=4096,
        )

        # 提取 JSON
        content = result.content
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = {"questions": []}

        # 自动审核方程式
        questions = data.get("questions", [])
        audit_results = []
        for q in questions:
            if q.get("has_equation") or any(
                kw in q.get("content", "")
                for kw in ["→", "=", "->", "方程式", "反应"]
            ):
                # 尝试提取并审核方程式
                eq_match = re.search(
                    r"([\d\w\(\)\+\s→=->]+)", q.get("content", "")
                )
                if eq_match:
                    audit = audit_chemical_equation(eq_match.group(1))
                    audit_results.append(
                        {
                            "question_idx": questions.index(q),
                            "equation": eq_match.group(1),
                            "audit": audit["overall_status"],
                        }
                    )

        await provider.close()

        return {
            "questions": questions,
            "total": len(questions),
            "audit_results": audit_results,
        }

    except Exception as e:
        await provider.close()
        return {"error": f"出题失败: {str(e)}", "questions": []}
