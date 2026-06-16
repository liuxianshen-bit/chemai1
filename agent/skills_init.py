"""
Skills 注册入口 — pydantic-ai 版本。
启动时导入 tools.py 的 10 个 tool_plain 函数。
"""
from agent.tools import TOOLS


def register_all_skills():
    names = [t.__name__ for t in TOOLS]
    print(f"[Agent] {len(names)} skills registered: {', '.join(names)}")
    return len(names)
