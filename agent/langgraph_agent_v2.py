"""ChemAI Single-Agent — one create_react_agent with all tools + GuardState.

Replaces the multi-agent coordinator+router+6-sub-agent architecture.
Single ReAct loop: LLM sees all tools, picks based on docstring descriptions.
GuardState provides dedup, call limits, and approval gating — same as v1.

Panel interrupt: when LLM calls show_exam_workbench, post_model_hook pauses the
graph via interrupt(). Frontend renders the panel, user fills params, clicks
"AI 出题" which resumes the graph with panel params → LLM calls generate_questions.
"""

import json
import logging

from langgraph.prebuilt import create_react_agent
from langgraph.graph import START, END

logger = logging.getLogger(__name__)

# ── Reuse from v1 (same GuardState, same tool wrapping, same model) ──
from agent.langgraph_agent import (
    get_langchain_model,
    GuardState,
    _make_guarded_tool,
    _make_request_approval_tool,
    TOOL_CALL_LIMITS,
    TOOL_APPROVAL_REQUIRED,
    _get_checkpointer,
    RECURSION_LIMIT as _V1_RECURSION_LIMIT,
)

# ── All tools ──
from agent.tools import TOOLS
from agent.browser_tools import (
    browse_navigate,
    browse_read,
    browse_click,
    browse_input,
    browse_screenshot,
)

RECURSION_LIMIT = 12

# Store context — set before agent invocation for tool access
_store_context = None


def set_store_context(store):
    global _store_context
    _store_context = store


def get_store_context():
    return _store_context


SYSTEM_PROMPT = """你是 ChemAI 化学教研助手。

你必须调用一个工具。阅读每个工具的描述（何时用/会发生什么/下一步/NOT for）来决定用哪个。
不确定时，选择最可能相关的工具并调用它。
禁止在不调用工具的情况下直接生成回复。

## 工具结果处理规则（严格执行）
- 工具返回的 total/result/questions 数据就是事实，直接引用展示
- 工具返回 total > 0 表示找到了结果，必须列出题目内容，禁止说"没有匹配""找不到"
- 工具返回 total = 0 时，如实告知用户没有找到，可以补充自己的知识说明
- 禁止用训练数据中的知识点总结替代工具返回的实际题目

## 出题规则
- 用户说"出题""出卷""生成题目"等任何出题意图 → 调 show_exam_workbench 打开面板
- 参数不全时也调 show_exam_workbench，预填已知参数（知识点、难度等）
- 不要在对话中追问用户参数——让面板处理"""

ALL_TOOLS = list(TOOLS) + [
    browse_navigate, browse_read, browse_click, browse_input, browse_screenshot,
]

_TOOL_BY_NAME = {t.__name__: t for t in ALL_TOOLS}


async def create_chemai_agent(
    persona: str = "tutor",
    provider: str = "deepseek",
    student_profile=None,
    intent_hints="",
    guard_state=None,
    store=None,
):
    """Create a single ReAct agent with persona-filtered tools.

    Returns (graph, guard_state). The guard_state is shared across all tool
    calls within one invocation — it tracks dedup, call limits, and approval.

    Panel tools (show_exam_workbench) trigger post_model_hook interrupt:
    graph pauses → frontend shows panel → user fills params → resume.
    """
    # Set store context for tool access
    if store is not None:
        set_store_context(store)
    from agent.agents import load_persona

    persona_config = load_persona(persona)
    available_skills = persona_config.get("available_skills", [])

    persona_tool_names = set(available_skills)
    domain_tools = [t for t in TOOLS if t.__name__ in persona_tool_names]
    browser_tools = [
        browse_navigate, browse_read, browse_click,
        browse_input, browse_screenshot,
    ]

    gs = guard_state or GuardState()
    approval_tools = set(TOOL_APPROVAL_REQUIRED) & persona_tool_names

    tools = [
        _make_guarded_tool(t, gs, t.__name__ in approval_tools)
        for t in domain_tools + browser_tools
    ]
    tools.append(_make_request_approval_tool(gs))

    model = get_langchain_model(provider)

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=SYSTEM_PROMPT,
    )

    logger.info(
        "[SingleAgent] Created — %d domain + %d browser tools, persona=%s",
        len(domain_tools), len(browser_tools), persona,
    )
    return agent, gs
