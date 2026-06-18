"""ChemAI Agent 工厂 — 按 persona + provider 创建 pydantic-ai Agent"""
import os
import yaml
from dataclasses import dataclass
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
        tool_names: Optional[list[str]] = None,
    ) -> Agent:
        """创建 Agent 实例。

        Args:
            persona: tutor | teacher | parent
            provider: deepseek | mimo | zhipu | dashscope
            deps: 可选的 ChemAIDeps（含 student profile 等）
            tool_names: 预分类的 tool 名列表。None 表示全量；传入则与 persona 的
                        available_skills 做交集；交集为空时自动回退全量
        """
        if persona not in self._personas:
            self._personas[persona] = load_persona(persona)

        persona_config = self._personas[persona]
        system_prompt = persona_config.get("system_prompt", "")
        available_skills = persona_config.get("available_skills", [])

        # Strip {tools} placeholder — pydantic-ai provides function definitions via API
        system_prompt = system_prompt.replace("{tools}", "")

        # Replace {student_profile} placeholder
        profile_str = "暂无学生信息"
        if deps and deps.student_profile:
            import json
            profile_str = json.dumps(deps.student_profile, ensure_ascii=False)
        system_prompt = system_prompt.replace("{student_profile}", profile_str)

        # Determine which tools to register
        if tool_names is not None:
            # Pre-classified: intersect with persona's available skills
            tools_set = set(tool_names)
            narrowed = [name for name in available_skills if name in tools_set]
            if not narrowed:
                # Empty intersection → fall back to all tools (worse than 30% misroute)
                skill_names = available_skills
            else:
                skill_names = narrowed
        else:
            skill_names = available_skills

        persona_tools = [
            _TOOL_BY_NAME[name]
            for name in skill_names
            if name in _TOOL_BY_NAME
        ]

        model = get_model(provider)

        # When tools are narrowed by the classifier, force tool_choice="required"
        # on the first model call so DeepSeek doesn't ignore tools and reply directly.
        # After the tool result comes back, switch to "auto" so the model can produce
        # a final text response. When no narrowing happened, keep default "auto".
        from pydantic_ai.settings import ModelSettings
        model_settings = None
        if tool_names is not None and skill_names:
            state = {"step": 0}
            def _model_settings(ctx):
                state["step"] += 1
                if state["step"] == 1:
                    return ModelSettings(tool_choice="required")
                return ModelSettings(tool_choice="auto")
            model_settings = _model_settings

        return Agent(
            model,
            system_prompt=system_prompt,
            deps_type=ChemAIDeps,
            tools=persona_tools,
            retries=1,
            model_settings=model_settings,
        )


# Global singleton
factory = ChemAIAgentFactory()
