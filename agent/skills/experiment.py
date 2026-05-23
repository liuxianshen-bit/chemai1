"""化学实验模拟 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="simulate_experiment",
    description="模拟高中化学实验，生成实验步骤、预测现象、写化学方程式、解释原理、提供安全提醒。",
    parameters={"experiment_name": "实验名称，如 钠与水的反应、铝热反应、乙酸乙酯的制备"},
)
async def simulate_experiment(experiment_name: str = "") -> dict:
    import os
    from dotenv import load_dotenv
    load_dotenv()

    from agent.provider.deepseek import DeepSeekProvider

    provider = DeepSeekProvider()

    system_prompt = """你是高中化学实验教学专家。为指定实验生成完整报告。

返回JSON:
{
  "experiment_name": "实验名称",
  "objectives": ["实验目的1", "实验目的2"],
  "equipment": ["仪器1", "药品1", ...],
  "steps": ["步骤1: ...", "步骤2: ..."],
  "expected_phenomena": ["现象1: ...", "现象2: ..."],
  "equations": ["化学方程式1", "化学方程式2"],
  "principles": ["原理1", "原理2"],
  "safety": ["安全提醒1", "安全提醒2"],
  "exam_tips": ["高考考点提示"]
}"""

    result = await provider.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请生成实验报告: {experiment_name}"},
        ],
        temperature=0.5,
        max_tokens=2048,
    )

    import json, re

    content = result.content
    json_match = re.search(r"\{[\s\S]*\}", content)

    await provider.close()

    if json_match:
        return json.loads(json_match.group())
    return {"experiment_name": experiment_name, "raw": content, "error": "JSON解析失败"}
