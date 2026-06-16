"""ChemAI Agent 工厂 — 按 persona + provider 创建 pydantic-ai Agent"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Optional

from pydantic_ai import Agent

from agent.deps import ChemAIDeps
from agent.models import get_model
from agent.tools import TOOLS


# Tool → name mapping
_TOOL_BY_NAME = {t.__name__: t for t in TOOLS}


def load_persona(name: str) -> dict:
    """加载 persona YAML 配置"""
    persona_dir = os.path.join(os.path.dirname(__file__), "personas")
    path = os.path.join(persona_dir, f"{name}.yaml")
    if not os.path.exists(path):
        path = os.path.join(persona_dir, "tutor.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ChemAIAgentFactory:
    """根据 persona + provider 创建配好的 pydantic-ai Agent"""

    def __init__(self):
        self._personas = {}

    def create_agent(
        self,
        persona: str = "tutor",
        provider: str = "deepseek",
        deps: Optional[ChemAIDeps] = None,
    ) -> Agent:
        """创建 Agent 实例。

        Args:
            persona: tutor | teacher | parent
            provider: deepseek | mimo | zhipu | dashscope
            deps: 可选的 ChemAIDeps（含 student profile 等）
        """
        if persona not in self._personas:
            self._personas[persona] = load_persona(persona)

        persona_config = self._personas[persona]
        system_prompt = persona_config.get("system_prompt", "")
        available_skills = persona_config.get("available_skills", [])

        # Replace {tools} placeholder with human-readable tool list
        tools_desc = ""
        for skill_name in available_skills:
            tool_fn = _TOOL_BY_NAME.get(skill_name)
            if tool_fn:
                tools_desc += f"\n  - **{skill_name}**: {tool_fn.__doc__ or ''}"
        system_prompt = system_prompt.replace("{tools}", tools_desc)

        # Replace {student_profile} placeholder
        profile_str = "暂无学生信息"
        if deps and deps.student_profile:
            import json
            profile_str = json.dumps(deps.student_profile, ensure_ascii=False)
        system_prompt = system_prompt.replace("{student_profile}", profile_str)

        # Filter tools by persona's available_skills
        persona_tools = [
            _TOOL_BY_NAME[name]
            for name in available_skills
            if name in _TOOL_BY_NAME
        ]

        model = get_model(provider)

        return Agent(
            model,
            system_prompt=system_prompt,
            deps_type=ChemAIDeps,
            tools=persona_tools,
        )


# Global singleton
factory = ChemAIAgentFactory()
