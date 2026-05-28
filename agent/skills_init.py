"""
Skills 注册入口 — 启动时导入所有 Skill 模块（通过装饰器自动注册到 registry）
"""
from .skill_registry import registry


def register_all_skills():
    # Agent skills (auto-register via @registry.register decorator)
    modules = [
        "agent.skills.balance",
        "agent.skills.search",
        "agent.skills.diagnose",
        "agent.skills.generate",
        "agent.skills.tutor",
        "agent.skills.experiment",
        "agent.skills.weekly_report",
        "agent.skills.import_exam",
        "agent.skills.practice",
        "agent.skills.web_search",
    ]
    for mod in modules:
        try:
            __import__(mod)
        except Exception as e:
            print(f"[Skills] {mod} failed: {e}")

    names = registry.list_skills()
    print(f"[Agent] {len(names)} skills registered: {', '.join(names)}")
    return len(names)
