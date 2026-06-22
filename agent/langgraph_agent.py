"""ChemAI LangGraph Agent — ReAct agent factory.

Replaces pydantic-ai Agent with LangGraph ReAct agent:
- LLM 自主决定 tool 调用顺序和次数 (not preset DAG)
- interrupt() 嵌入 request_approval tool
- Tool 集合固定 per persona YAML (保证 interrupt/resume 兼容)
- Guardrails: recursion_limit, tool dedup, requires_approval enforcement, _route stripping
"""
import json, os, logging
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
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
    "generate_questions": 5,
    "diagnose_barrier": 2,
    "weekly_report": 2,
    "balance_equation": 3,
    "chemistry_tutor": 3,
    "simulate_experiment": 2,
    "import_exam_paper": 1,
    "assign_adaptive_practice": 1,
    "save_to_bank": 1,
}


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


def _make_guarded_tool(fn, guard_state: GuardState, requires_approval: bool = False):
    """Wrap a tool with guardrail enforcement, preserving LLM-facing schema.

    Guardrails applied (per D8/D9):
    1. Dedup: skip duplicate (same tool + same args) calls
    2. Requires-approval: block destructive tools unless request_approval was called first
    3. _route stripping: remove _route from tool result before it reaches LLM context
    """
    base_tool = lc_tool(fn)

    async def _guarded(**kwargs) -> str:
        name = fn.__name__

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

        # ── Strip _route from LLM context ──
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if isinstance(data, dict) and "_route" in data:
                    guard_state.last_route = data.pop("_route")
                    return json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(result, dict) and "_route" in result:
            guard_state.last_route = result.pop("_route")

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


def build_persona_prompt(persona: str, student_profile: dict | None = None,
                         intent_hints: str = "") -> str:
    """Build system prompt from persona YAML + optional hints."""
    from agent.agents import load_persona

    cfg = load_persona(persona)
    prompt = cfg.get("system_prompt", "")

    # Replace {tools} placeholder (not needed, LangGraph handles tool binding)
    prompt = prompt.replace("{tools}", "")

    # Replace {student_profile}
    profile_str = "暂无学生信息"
    if student_profile:
        profile_str = json.dumps(student_profile, ensure_ascii=False)
    prompt = prompt.replace("{student_profile}", profile_str)

    # Append intent hints
    if intent_hints:
        prompt += f"\n\n## 工具推荐\n{intent_hints}\n以上是推荐工具，你可以使用它们，也可以根据需要使用其他工具。自己判断最合适的。"

    # Add guardrail instructions
    prompt += """
## 行为规则（必须遵守）
1. 以下情况必须调用工具，不能空口回答：
   - 出题/生成题目 → generate_questions
   - 搜索真题 → search_exam_bank
   - 诊断/学情分析 → diagnose_barrier
   - 配平方程式 → balance_equation
   - 模拟实验 → simulate_experiment
   - 导入试卷 → import_exam_paper
   - 布置练习 → assign_adaptive_practice
   - 生成周报 → weekly_report
   - 联网搜索最新信息 → web_search
   - 化学知识辅导 → chemistry_tutor
   - 保存题目到题库 → save_to_bank
2. 即使你觉得可以直接回答，如果任务匹配上述场景，也要调用工具。
3. 只有纯粹的闲聊（你好/再见/今天天气）才可以不调工具。
4. 信息不足时先反问，不要猜参数。
5. request_approval 只在出完题或准备执行发布/导入/布置等操作时调用。
6. **效率规则**：
   - 每个搜索类工具（search_exam_bank、web_search）最多调 1-2 次，拿到结果后直接基于结果回答或出题，不要反复搜索
   - 如果一次搜索已返回足够数据，立即进入下一步（出题/回答），不要换关键词再搜
   - 出题前先想清楚：是否需要搜索？如果用户已经给了明确的知识点范围，直接出题即可
7. **保存规则**：
   - 如果用户没有指定具体学生（只是说要出题），出完题后必须调用 save_to_bank 将题目保存到题库
   - 保存后告诉用户题目存在哪个文件夹（set_name），并引导用户去考试工作台查看"""

    return prompt


def create_chemai_agent(persona: str = "tutor", provider: str = "deepseek",
                        student_profile: dict | None = None,
                        intent_hints: str = "",
                        guard_state: GuardState = None) -> tuple["CompiledGraph", GuardState]:
    """Create a ChemAI ReAct agent with guardrails.

    Args:
        persona: tutor | teacher | parent
        provider: deepseek | mimo | zhipu | dashscope
        student_profile: student info dict for system prompt
        intent_hints: classifier recommendations injected into prompt
        guard_state: shared GuardState for dedup/approval tracking (auto-created if None)

    Returns:
        (Compiled LangGraph ReAct agent, GuardState)
    """
    if guard_state is None:
        guard_state = GuardState()
    tools = get_tools_for_persona(persona, guard_state)
    model = get_langchain_model(provider)
    prompt = build_persona_prompt(persona, student_profile, intent_hints)

    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        checkpointer=MemorySaver(),
    )
    return agent, guard_state
