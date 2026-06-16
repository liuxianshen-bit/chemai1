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


# Keyword → tool mapping for pre-filtering (narrows tools before LLM call)
_KEYWORD_TOOL_MAP = [
    (["出题", "生成", "出", "练习", "组卷", "题目", "题", "布置"], "generate_questions"),
    (["搜", "搜索", "查", "找", "真题", "高考", "题库"], "search_exam_bank"),
    (["联网", "最新", "动态", "资讯", "新闻"], "web_search"),
    (["诊断", "障碍", "学情", "薄弱"], "diagnose_barrier"),
    (["讲解", "讲", "概念", "什么是", "怎么", "如何", "为什么", "教我", "辅导", "解释"], "chemistry_tutor"),
    (["实验", "模拟", "反应现象"], "simulate_experiment"),
    (["配平", "方程式", "审核", "化学式"], "balance_equation"),
    (["周报", "本周", "学习报告", "家长", "汇报"], "weekly_report"),
    (["导入", "试卷", "PDF", "pdf", "上传"], "import_exam_paper"),
    (["自适应", "布置练习", "个性化练习"], "assign_adaptive_practice"),
]

# Avoid over-matching: if a short keyword (1-2 chars) would match too broadly, require a companion keyword
_SHORT_KW_REQUIRE_COMPANION = {"出", "题", "讲", "搜"}


def classify_tools(message: str, available_skills: list[str]) -> list:
    """Keyword-based tool pre-filter. Returns narrowed tool list (max 3)."""
    matched = []
    for keywords, tool_name in _KEYWORD_TOOL_MAP:
        if tool_name not in available_skills:
            continue
        if any(kw in message for kw in keywords):
            if tool_name not in matched:
                matched.append(tool_name)
    # If nothing matched, return all available (let LLM decide)
    if not matched:
        return available_skills
    # If only 1 tool matched, return just that one (force tool use)
    # Otherwise return up to 2 best matches
    if len(matched) == 1:
        return matched
    return matched[:2]


class ChemAIAgentFactory:
    """根据 persona + provider 创建配好的 pydantic-ai Agent"""

    def __init__(self):
        self._personas = {}

    def create_agent(
        self,
        persona: str = "tutor",
        provider: str = "deepseek",
        deps: Optional[ChemAIDeps] = None,
        user_message: str = "",
    ) -> Agent:
        """创建 Agent 实例。

        Args:
            persona: tutor | teacher | parent
            provider: deepseek | mimo | zhipu | dashscope
            deps: 可选的 ChemAIDeps（含 student profile 等）
            user_message: 用户消息，用于 keyword pre-filter
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

        # Pre-filter tools by keyword match (narrow tools for better LLM selection)
        if user_message:
            narrowed_skills = classify_tools(user_message, available_skills)
        else:
            narrowed_skills = available_skills

        persona_tools = [
            _TOOL_BY_NAME[name]
            for name in narrowed_skills
            if name in _TOOL_BY_NAME
        ]

        model = get_model(provider)
        from pydantic_ai.settings import ModelSettings

        # Force tool choice when keywords matched specific tools
        force_tool = (
            user_message
            and len(narrowed_skills) < len(available_skills)
            and len(narrowed_skills) > 0
        )
        model_settings = ModelSettings(
            tool_choice="required" if force_tool else "auto"
        )

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
