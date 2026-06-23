"""ChemAI LangGraph Agent — ReAct agent factory.

Replaces pydantic-ai Agent with LangGraph ReAct agent:
- LLM 自主决定 tool 调用顺序和次数 (not preset DAG)
- interrupt() 嵌入 request_approval tool
- Tool 集合固定 per persona YAML (保证 interrupt/resume 兼容)
- Guardrails: recursion_limit, tool dedup, requires_approval enforcement, _route stripping
"""
import json, os, logging
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

# Shared checkpointer — module-level so state persists across HTTP requests.
# If this were created inside create_chemai_agent(), each request would get
# a fresh MemorySaver with no prior state → thread_id lookups always miss.
_checkpointer = MemorySaver()
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool as lc_tool, StructuredTool

logger = logging.getLogger(__name__)

# ── Guardrail config ──
TOOL_APPROVAL_REQUIRED = {"assign_adaptive_practice", "import_exam_paper"}
RECURSION_LIMIT = 8

# Per-tool call limits (防止 LLM 在同一轮里反复调同一工具浪费 token)
TOOL_CALL_LIMITS: dict[str, int] = {
    "search_exam_bank": 3,
    "web_search": 2,
    "show_exam_workbench": 3,
    "diagnose_barrier": 2,
    "weekly_report": 2,
    "balance_equation": 3,
    "chemistry_tutor": 3,
    "simulate_experiment": 2,
    "import_exam_paper": 1,
    "assign_adaptive_practice": 1,
    "save_to_bank": 1,
}

# Per-tool required context fields. If any are missing from the tool call args,
# the call is blocked before execution with a "请先向用户确认" message.
# This makes "反问用户" a structural gate, not a prompt hope.
TOOL_PREREQUISITES: dict[str, list[str]] = {
    "show_exam_workbench": ["knowledge_points", "question_types"],
    "search_exam_bank": ["keyword"],
    "diagnose_barrier": ["student_id_or_class_id"],
    "weekly_report": ["student_id_or_class_id"],
    "assign_adaptive_practice": ["student_id_or_class_id"],
}

# Keywords so generic they don't count as a specific request.
# If search_exam_bank is called with only these as keyword, block and ask for specifics.
# These are checked via substring containment — "找几个高考真题" contains "高考真题".
VAGUE_KEYWORDS: list[str] = [
    "高考真题", "真题", "化学题", "高考化学", "高中化学",
    "高考", "找几个", "来几道", "题目", "搜题", "找题",
    "出几道", "几道题", "出题",
]

def _is_keyword_too_vague(keyword: str) -> bool:
    """Check if a search keyword is too generic to produce useful results."""
    kw = keyword.strip()
    if len(kw) <= 2:  # single character or empty after strip
        return True
    for vague in VAGUE_KEYWORDS:
        if vague in kw:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# Guard state — per-agent-invocation, shared across all tools
# ═══════════════════════════════════════════════════════════════════════

class GuardState:
    """Per-invocation guard state: dedup, approval tracking, _route storage, call limits."""
    def __init__(self):
        self.seen_calls: set[str] = set()
        self.call_counts: dict[str, int] = {}
        self.approved: bool = False
        self.last_route: dict | None = None
        self.last_component: dict | None = None

    def check_dedup(self, name: str, kwargs: dict) -> bool:
        key = f"{name}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        if key in self.seen_calls:
            return True
        self.seen_calls.add(key)
        return False

    def check_limit(self, name: str) -> str | None:
        """Check per-tool call limit. Returns error message if exceeded, None if ok."""
        limit = TOOL_CALL_LIMITS.get(name)
        if limit is None:
            return None
        count = self.call_counts.get(name, 0) + 1
        self.call_counts[name] = count
        if count > limit:
            return f"已调用 {name} {count} 次（上限 {limit} 次），请基于已有结果继续，不要重复调用。"
        return None

    def check_prerequisites(self, name: str, kwargs: dict) -> str | None:
        """Check required context fields before tool execution.
        Returns error message if prerequisites not met, None if OK.
        """
        prereqs = TOOL_PREREQUISITES.get(name, [])
        for field in prereqs:
            # Special case: "student_id_or_class_id" checks multiple params
            if field == "student_id_or_class_id":
                has_student = (kwargs.get("student_id", "") or "").strip()
                has_name = (kwargs.get("student_name", "") or "").strip()
                has_class = (kwargs.get("class_id", "") or "").strip()
                has_class_name = (kwargs.get("class_name", "") or "").strip()
                if not (has_student or has_name or has_class or has_class_name):
                    return "缺少必要信息：请先向用户确认学生姓名/学号或班级。"
                continue
            # Special case: "keyword" field checks specificity (not just non-empty)
            if field == "keyword":
                val = (kwargs.get("keyword", "") or "").strip()
                if not val or _is_keyword_too_vague(val):
                    return "搜索关键词太宽泛。请先向用户确认：需要哪个具体知识点的真题？哪一年的？什么难度？"
                continue
            val = kwargs.get(field, "")
            if not val or not str(val).strip():
                return f"缺少必要信息: {field}。请先向用户确认。"
        return None


def _make_guarded_tool(fn, guard_state: GuardState, requires_approval: bool = False):
    """Wrap a tool with guardrail enforcement, preserving LLM-facing schema.

    Guardrails applied (per D8/D9):
    0. Prerequisites: block tools missing required context fields (e.g., generate_questions without knowledge_points)
    1. Call limit: block excessive repeated calls per tool type
    2. Dedup: skip duplicate (same tool + same args) calls
    3. Requires-approval: block destructive tools unless request_approval was called first
    4. _route stripping: remove _route from tool result before it reaches LLM context
    """
    base_tool = lc_tool(fn)

    async def _guarded(**kwargs) -> str:
        name = fn.__name__

        # ── Prerequisite check (must be FIRST — block before any other check) ──
        prereq_msg = guard_state.check_prerequisites(name, kwargs)
        if prereq_msg:
            return json.dumps({"error": prereq_msg, "missing_prerequisites": True}, ensure_ascii=False)

        # ── Call limit check (防止同一工具反复调用浪费 token) ──
        limit_msg = guard_state.check_limit(name)
        if limit_msg:
            return json.dumps({"error": limit_msg, "limit_exceeded": True}, ensure_ascii=False)

        # ── Dedup check ──
        if guard_state.check_dedup(name, kwargs):
            return json.dumps({"error": "检测到重复调用，已跳过", "dedup_skipped": True}, ensure_ascii=False)

        # ── Requires-approval check ──
        if requires_approval and not guard_state.approved:
            return json.dumps({"error": "此操作需要老师确认，请先调用 request_approval",
                               "requires_approval_blocked": True}, ensure_ascii=False)

        # ── Execute original tool ──
        result = await fn(**kwargs)

        # ── Strip _route/_component from LLM context ──
        stripped = False
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if isinstance(data, dict):
                    if "_route" in data:
                        guard_state.last_route = data.pop("_route")
                        stripped = True
                    if "_component" in data:
                        guard_state.last_component = data.pop("_component")
                        stripped = True
                    if stripped:
                        return json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(result, dict):
            if "_route" in result:
                guard_state.last_route = result.pop("_route")
            if "_component" in result:
                guard_state.last_component = result.pop("_component")

        return result

    return StructuredTool(
        name=base_tool.name,
        description=base_tool.description,
        args_schema=base_tool.args_schema,
        coroutine=_guarded,
    )


def get_tools_for_persona(persona: str, guard_state: GuardState = None) -> list:
    """Load persona YAML, return LangChain tools (fixed set per persona) with guardrails."""
    from agent.agents import load_persona
    from agent.tools import TOOLS

    if guard_state is None:
        guard_state = GuardState()

    cfg = load_persona(persona)
    available = set(cfg.get("available_skills", []))

    _tool_by_name = {t.__name__: t for t in TOOLS}

    tools = []
    for name, fn in _tool_by_name.items():
        if name in available:
            wrapped = _make_guarded_tool(
                fn, guard_state,
                requires_approval=(name in TOOL_APPROVAL_REQUIRED),
            )
            tools.append(wrapped)

    # Always add request_approval (with guard but marks approved on execution)
    tools.append(_make_request_approval_tool(guard_state))

    logger.info(f"[LangGraph] {persona}: {len(tools)} tools registered "
                f"(persona: {len(tools)-1}, +request_approval)")
    return tools


def _make_request_approval_tool(guard_state: GuardState):
    """Create the request_approval tool with interrupt() inside."""

    @lc_tool
    async def request_approval(message: str, context: str = "") -> str:
        """向老师请求确认。生成内容后需要老师审核时调用。
        只在真正需要人为判断时调，不要每步都问。
        例如：出完题后请老师预览、导入试卷前确认来源、布置练习前确认班级。"""
        guard_state.approved = True
        interrupt({
            "type": "approval",
            "message": message,
            "context": context,
        })
        return "approved"

    return request_approval


def get_langchain_model(provider: str) -> ChatOpenAI:
    """Create ChatOpenAI instance for the given provider."""
    api_keys = {
        "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        "mimo": os.getenv("XIAOMI_API_KEY", ""),
        "zhipu": os.getenv("ZHIPU_API_KEY", ""),
        "dashscope": os.getenv("DASHSCOPE_API_KEY", ""),
    }
    configs = {
        "deepseek": {"model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
        "mimo": {"model": "mimo-v2.5", "base_url": "https://api.xiaomimimo.com/v1"},
        "zhipu": {"model": "GLM-4-Flash", "base_url": "https://open.bigmodel.cn/api/paas/v4"},
        "dashscope": {"model": "qwen-turbo", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    }
    cfg = configs.get(provider, configs["deepseek"])
    return ChatOpenAI(
        model=cfg["model"],
        api_key=api_keys.get(provider, ""),
        base_url=cfg["base_url"],
        temperature=0.3,
        max_tokens=4096,
    )


# ═══════════════════════════════════════════════════════════════════════
# Prompt builders — four-layer structured context
# ═══════════════════════════════════════════════════════════════════════

def _build_product_context() -> str:
    """[PRODUCT] section — same for all personas."""
    return """[PRODUCT]
你是 ChemAI，一个高中化学 AI 教学助手。你可以帮用户完成以下四类任务：

1. **聊天辅导** — 在对话中讲解化学概念、引导解题思路、答疑解惑。适合学生提问。
2. **考试工作台** — 搜索历年高考真题、根据知识点出题组卷、将题目保存到题库文件夹管理。适合老师准备考试。
3. **学情诊断** — 分析单个学生或整个班级的学习障碍（概念理解/审题/表述），找出薄弱环节。适合老师了解学情。
4. **学习报告** — 生成学生或班级的周报、学情报告，面向家长通俗易懂。

用户可能是老师（管理班级、出卷、诊断）、学生（提问、练习）、或家长（了解学习情况）。
**关键原则：如果用户没说清楚（学生是谁、哪个知识点、什么难度、几道题），请先反问，不要猜测。**"""


def _build_role_context(persona: str) -> str:
    """[ROLE] section — persona-specific framing from YAML."""
    from agent.agents import load_persona

    cfg = load_persona(persona)
    yaml_prompt = cfg.get("system_prompt", "")

    # Strip tool-mapping bullet lines (keep role framing, remove tool rules)
    lines = yaml_prompt.split("\n")
    kept = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that map user intent to specific tools
        if any(kw in stripped for kw in ["→", "->", "调用工具", "工具推荐", "{tools}"]):
            continue
        # Skip persona YAML placeholder
        if stripped == "{student_profile}":
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()

    if not cleaned:
        cleaned = "你是高中化学教学助手。"

    return f"[ROLE]\n{cleaned}"


def _build_tool_context(tools: list) -> str:
    """[TOOLS] section — auto-assembled from StructuredTool.description."""
    import inspect

    lines = ["[TOOLS]"]
    for t in tools:
        desc = getattr(t, "description", "") or ""
        if "何时用" not in desc:
            continue  # skip internal guardrail tools like request_approval
        lines.append(desc)
        lines.append("")  # blank line between tools

    return "\n".join(lines).rstrip()


def _build_reasoning_anchor() -> str:
    """[REASONING] section — 3-question self-check before every action."""
    return """[REASONING]
每次行动前，快速自问：
1. 用户真正想要的结果是什么？（出题→考试工作台 / 答疑→对话中 / 诊断→诊断页 / 报告→对话或跳转）
2. 我现在掌握的信息够做这件事吗？（不够就先反问用户）
3. 做完这一步后，用户还需要什么？（保存？跳转？继续出题？报告？）"""


def build_persona_prompt(persona: str, student_profile: dict | None = None,
                         intent_hints: str = "") -> str:
    """Build system prompt: [PRODUCT] + [ROLE] + optional profile/hints + [REASONING] + [TOOLS].
    The hardcoded behavior rules section is REMOVED — code guardrails (GuardState,
    TOOL_CALL_LIMITS, check_prerequisites) enforce constraints at the architecture level.
    """
    from agent.langgraph_agent import get_tools_for_persona

    sections = []

    # ── Layer 1: Product context ──
    sections.append(_build_product_context())

    # ── Layer 2: Role context ──
    sections.append(_build_role_context(persona))

    # ── Optional: Student profile ──
    if student_profile:
        profile_str = json.dumps(student_profile, ensure_ascii=False)
        sections.append(f"[PROFILE]\n{profile_str}")

    # ── Optional: Classifier hints ──
    if intent_hints:
        sections.append(f"[HINTS]\n{intent_hints}")

    # ── Layer 3: Reasoning anchor (before tools — guides selection) ──
    sections.append(_build_reasoning_anchor())

    # ── Layer 4: Tool context (last — recency bias for selection) ──
    persona_tools = get_tools_for_persona(persona)
    sections.append(_build_tool_context(persona_tools))

    return "\n\n".join(sections).strip()


def create_chemai_agent(persona: str = "tutor", provider: str = "deepseek",
                        student_profile: dict | None = None,
                        intent_hints: str = "",
                        guard_state: GuardState = None) -> tuple["CompiledGraph", GuardState]:
    """Create a ChemAI ReAct agent with router + check nodes.

    Graph structure:
        START → llm → router → check → tools → llm (loop)
                        ↓        ↓        ↓ fail
                       END    redirect   inject msg → llm

    router: redirects search_exam_bank → navigate_to_exam_workbench
            when user has already provided exam parameters
    check:  blocks tool calls when prerequisites are missing
    """
    from langgraph.graph import StateGraph, MessagesState, START, END
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

    if guard_state is None:
        guard_state = GuardState()
    tools = get_tools_for_persona(persona, guard_state)
    model = get_langchain_model(provider)
    prompt = build_persona_prompt(persona, student_profile, intent_hints)
    model_with_tools = model.bind_tools(tools)

    # ── Helpers ──
    def _user_text(state):
        """Extract recent user message text (excluding injected block messages)."""
        user_msgs = [m for m in state["messages"]
                     if isinstance(m, HumanMessage)
                     and not getattr(m, 'content', '').startswith("以下工具调用")
                     and not getattr(m, 'content', '').startswith("检测到")]
        return " ".join([m.content for m in user_msgs[-3:]])

    def _has_exam_params(text):
        """Check if user has given enough specificity for exam generation."""
        has_kp = any(kp in text for kp in ["氧化还原", "电化学", "有机", "化学平衡", "盐类水解",
            "元素周期", "物质结构", "化学反应", "离子反应", "元素化合物", "金属", "非金属",
            "电解质", "水解", "电离", "原电池", "电解池", "晶体", "分子", "原子", "摩尔",
            "方程式", "同分异构", "官能团", "取代", "加成", "消去", "酯化", "聚合",
            "工业流程", "阿伏加德罗", "勒夏特列", "配平", "实验", "计算"])
        has_types = any(t in text for t in ["选择题", "填空题", "计算题", "实验题", "推断题", "选择", "填空"])
        return has_kp or has_types

    # ── Node: llm ──
    def _llm_node(state):
        msgs = list(state["messages"])
        if not any(getattr(m, 'type', '') == 'system' for m in msgs):
            msgs = [SystemMessage(content=prompt)] + msgs
        resp = model_with_tools.invoke(msgs)
        return {"messages": [resp]}

    # ── Node: router — redirect wrong tool choices ──
    def _router_node(state):
        last = state["messages"][-1]
        tc_list = getattr(last, 'tool_calls', []) or []
        if not tc_list:
            return {}

        search_calls = [tc for tc in tc_list if tc.get("name") == "search_exam_bank"]
        if not search_calls:
            return {}

        text = _user_text(state)
        if _has_exam_params(text):
            # Strip tool_calls from the AIMessage and inject redirect instruction.
            # Same ID → LangGraph replaces the original message in state.
            # This avoids an extra LLM round-trip (no double response).
            return {"messages": [
                AIMessage(
                    content="好的，您已提供了出题所需的参数。"
                            "现在直接为您跳转到考试工作台自动生成题目。",
                    id=last.id
                )
            ]}
        return {}

    # ── Node: check — pre-tool structural gate ──
    def _check_node(state):
        last = state["messages"][-1]
        # Skip if already processed (AIMessage without tool_calls from replacement)
        if isinstance(last, AIMessage) and not getattr(last, 'tool_calls', None):
            return {}
        tc_list = getattr(last, 'tool_calls', []) or []
        if not tc_list:
            return {}

        issues = []
        for tc in tc_list:
            name = tc.get("name", "")
            args = tc.get("args", {})
            err = guard_state.check_prerequisites(name, args)
            if err:
                issues.append(f"- {name}: {err}")

        if issues:
            # Replace AIMessage: strip tool_calls, keep existing text + add block notice.
            # Same ID → LangGraph replaces the original. No extra LLM round-trip.
            existing_text = last.content or ""
            block_text = "（以下工具调用被拦截：\n" + "\n".join(issues) + "\n请先向用户确认缺失的信息。）"
            return {"messages": [
                AIMessage(content=existing_text + "\n\n" + block_text, id=last.id)
            ]}
        return {}

    # ── Node: tools ──
    _tool_node = ToolNode(tools)

    # ── Routing ──
    def _route_after_llm(state):
        last = state["messages"][-1]
        if getattr(last, 'tool_calls', None):
            return "router"
        return END

    def _route_after_router(state):
        last = state["messages"][-1]
        # If AIMessage has no tool_calls → it was replaced by router → END
        if isinstance(last, AIMessage) and not getattr(last, 'tool_calls', None):
            return END
        return "check"

    def _route_after_check(state):
        last = state["messages"][-1]
        # If AIMessage has no tool_calls → it was replaced by check → END
        if isinstance(last, AIMessage) and not getattr(last, 'tool_calls', None):
            return END
        return "tools"

    # ── Build ──
    builder = StateGraph(MessagesState)
    builder.add_node("llm", _llm_node)
    builder.add_node("router", _router_node)
    builder.add_node("check", _check_node)
    builder.add_node("tools", _tool_node)

    builder.add_edge(START, "llm")
    builder.add_conditional_edges("llm", _route_after_llm, {"router": "router", END: END})
    builder.add_conditional_edges("router", _route_after_router, {"llm": "llm", "check": "check", END: END})
    builder.add_conditional_edges("check", _route_after_check, {"llm": "llm", "tools": "tools", END: END})
    builder.add_edge("tools", "llm")

    return builder.compile(checkpointer=_checkpointer), guard_state
