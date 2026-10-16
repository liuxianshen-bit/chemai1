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

# Use the shared AsyncSqliteSaver from guard (persists across requests and restarts)
_v2_checkpointer = None

async def _get_v2_checkpointer():
    global _v2_checkpointer
    if _v2_checkpointer is None:
        from agent.guard import _get_checkpointer
        _v2_checkpointer = await _get_checkpointer()
    return _v2_checkpointer

logger = logging.getLogger(__name__)

# ── Guard infrastructure (shared with v1) ──
from agent.guard import (
    get_langchain_model,
    GuardState,
    _make_guarded_tool,
    _make_request_approval_tool,
    TOOL_APPROVAL_REQUIRED,
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

## 关键区分：学习计划 vs 布置练习
- 用户说"学习计划""学习方案""学习规划""制定计划" → generate_learning_plan（生成文本型学习方案：周目标、日任务、干预建议）
- 用户说"出题""布置练习""针对性练习""出几道题""做题" → assign_adaptive_practice（生成练习题：题目、选项、答案）
- 两词同时出现时，看用户核心诉求：要"方案/计划"走 generate_learning_plan，要"题/练习"走 assign_adaptive_practice

## 输出规则
- 工具返回了引导性回复后（如"请把方程式发来"），用一个简短的过渡语句承接（如"试试发过来吧！"），不要逐字重复工具的引导内容。
- 工具返回了实质性内容（如实验结果、题目解析）后，直接展示，不要在前面加"好的，我来为你..."。
- generate_learning_plan 返回后，不要在文本中重复输出方案内容，也不要额外调用 diagnose_barrier 或 show_diagnosis——方案已内联渲染完整信息。

## 工具结果处理
- search_exam_bank 返回 STATUS="FOUND" → 逐题展示，禁止说"没找到"，禁止再调 web_search
- search_exam_bank 返回 STATUS="NOT_FOUND" → 告知用户本地题库暂无，自动调用 web_search 搜索网上相关真题
- web_search 也无结果 → 用你的知识总结该知识点的考点和常考方向，最后建议用户用出题面板自主生成

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

    # Build persona-aware system prompt
    persona_prompt = persona_config.get("system_prompt", "").strip()

    # Build student context string and inject into prompt
    student_context = ""
    if student_profile and isinstance(student_profile, dict):
        sp = student_profile
        name = sp.get("name", "")
        sid = sp.get("student_id", "")
        barrier = sp.get("barrier", {})
        exercises = sp.get("exercises_completed", 0)
        if name:
            parts = [f"当前孩子: {name}（学号 {sid}）" if sid else f"当前孩子: {name}"]
            dom = max(barrier, key=barrier.get) if barrier else ""
            dom_labels = {"concept": "概念理解", "reading": "审题仔细度", "expression": "答题表述"}
            if dom:
                parts.append(f"主要学习特点: {dom_labels.get(dom, dom)}")
            if exercises:
                parts.append(f"已完成练习: {exercises} 次")
            student_context = "。".join(parts)

    if persona_prompt:
        prompt = persona_prompt.replace("{student_context}", student_context or "正在查看孩子的学习情况。")
        prompt = prompt + "\n\n## 工具使用\n你必须调用工具来处理用户问题。阅读每个工具的 docstring（何时用/会发生什么/下一步/NOT for）来选择。不确定时选择最相关的工具并调用它。禁止不调工具直接回复。\n\n## 输出规则（严格遵守）\n1. 工具返回了完整引导回复（如 ionic_equation_tutor/stoichiometry_tutor/chemistry_tutor/simulate_experiment）后，最多说一句极短的过渡（如「试试看吧！」），不要把工具内容用自己的话重说一遍。\n2. 不要问「你是学生还是老师」—— persona 已经告诉你了。\n3. 工具返回的内容就是给学生的回复，你不要再复述、总结、或添加类似内容。"
    else:
        prompt = SYSTEM_PROMPT

    # Build tool set: persona YAML available_skills acts as whitelist filter
    # on top of TOOL_META auto-registration
    from agent.tools import TOOL_META as _TOOL_META
    yaml_skills = set(available_skills) if available_skills else None
    auto_skills = set(t.__name__ for t, meta in _TOOL_META.items() if persona in meta.get("personas",[]))
    if yaml_skills:
        persona_tool_names = auto_skills & yaml_skills
        if not persona_tool_names:
            persona_tool_names = auto_skills
    else:
        persona_tool_names = auto_skills
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

    checkpointer = await _get_v2_checkpointer()
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        checkpointer=checkpointer,
    )

    logger.info(
        "[SingleAgent] Created — %d domain + %d browser tools, persona=%s",
        len(domain_tools), len(browser_tools), persona,
    )
    return agent, gs
