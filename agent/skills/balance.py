"""方程式配平审核 Skill"""
from agent.skill_registry import registry


@registry.register(
    name="balance_equation",
    description="审核化学方程式是否配平，检查左右两侧各元素原子数量是否相等。返回 is_balanced、message、左右元素计数的详细报告。",
    parameters={"equation": "化学方程式字符串，如 2H2 + O2 = 2H2O 或 Fe + O2 = Fe2O3"},
)
async def balance_equation(equation: str) -> dict:
    from app.services.chemical_balance import audit_chemical_equation

    return audit_chemical_equation(equation)
