"""ChemAI Agent Guard Infrastructure — shared by v1 and v2 agent architectures.

GuardState provides per-invocation safety: deduplication, call limits,
prerequisite checks, and approval gating for destructive tools.

Extracted from langgraph_agent.py (v1 multi-agent) so both v1 and v2 can
import from a neutral module without circular dependencies.
"""

import json
import logging

logger = logging.getLogger(__name__)

# ── Tool call limits (lazy-loaded from TOOL_META to avoid circular imports) ──
TOOL_CALL_LIMITS: dict[str, int] = {}
_LIMITS_INITIALIZED = False

def _ensure_call_limits():
    global TOOL_CALL_LIMITS, _LIMITS_INITIALIZED
    if _LIMITS_INITIALIZED:
        return
    try:
        from agent.tools import TOOL_META
        TOOL_CALL_LIMITS = {t.__name__: m["call_limit"] for t, m in TOOL_META.items()}
    except ImportError:
        pass
    _LIMITS_INITIALIZED = True


# ── Approval gating ──
TOOL_APPROVAL_REQUIRED = {"assign_adaptive_practice", "delete_bank"}

# ── Recursion limits ──
RECURSION_LIMIT_V1 = 8
RECURSION_LIMIT_V2 = 12


# ═══════════════════════════════════════════════════════════════════════
# GuardState
# ═══════════════════════════════════════════════════════════════════════

class GuardState:
    """Per-invocation safety state shared across all tool calls within one request.

    Tracks: dedup (same tool+args within 5s = skip), call limits (per-tool max),
    prerequisite checks (required args present), and approval gating (destructive
    tools must first call request_approval).
    """

    def __init__(self):
        self.seen_calls: set[str] = set()
        self.call_counts: dict[str, int] = {}
        self.approved: bool = False
        self.last_route: dict | None = None
        self.last_component: dict | None = None

    def check_dedup(self, name: str, kwargs: dict) -> bool:
        """Return True if this exact call was already made (dedup hit)."""
        key = f"{name}:{json.dumps(kwargs, sort_keys=True, ensure_ascii=False)}"
        if key in self.seen_calls:
            return True
        self.seen_calls.add(key)
        return False

    def check_limit(self, name: str) -> str | None:
        """Return error message if call limit exceeded, else None."""
        _ensure_call_limits()
        limit = TOOL_CALL_LIMITS.get(name)
        if limit is None:
            return None
        count = self.call_counts.get(name, 0) + 1
        self.call_counts[name] = count
        if count > limit:
            return f"已调用 {name} {count} 次（上限 {limit} 次），请基于已有结果继续。"
        return None

    def check_prerequisites(self, name: str, kwargs: dict) -> str | None:
        """Return error message if required params are missing, else None."""
        prereqs = {
            "show_exam_workbench": [],
            "search_exam_bank": ["keyword"],
            "diagnose_barrier": ["student_id_or_class_id"],
            "weekly_report": ["student_id_or_class_id"],
            "assign_adaptive_practice": ["student_id_or_class_id"],
        }
        for field in prereqs.get(name, []):
            if field == "student_id_or_class_id":
                if not any((kwargs.get(k, "") or "").strip() for k in
                           ("student_id", "student_name", "class_id", "class_name")):
                    return "缺少必要信息：请先向用户确认学生姓名/学号或班级。"
                continue
            if field == "keyword":
                val = (kwargs.get("keyword", "") or "").strip()
                if not val or len(val) <= 2:
                    return "搜索关键词太宽泛。请先向用户确认：需要哪个具体知识点的真题？"
                continue
            if not (kwargs.get(field, "") or "").strip():
                return f"缺少必要信息: {field}。请先向用户确认。"
        return None


# ═══════════════════════════════════════════════════════════════════════
# Tool Wrappers
# ═══════════════════════════════════════════════════════════════════════

def _make_guarded_tool(fn, guard_state: GuardState, requires_approval: bool = False):
    """Wrap a tool function with GuardState safety checks.

    Applies: prerequisite check → call limit → dedup → approval gating.
    Strips _route and _component fields from result before returning.
    """
    from langchain_core.tools import tool as lc_tool, StructuredTool

    base_tool = lc_tool(fn)

    async def _guarded(**kwargs) -> str:
        name = fn.__name__
        if (msg := guard_state.check_prerequisites(name, kwargs)):
            return json.dumps({"error": msg, "missing_prerequisites": True}, ensure_ascii=False)
        if (msg := guard_state.check_limit(name)):
            return json.dumps({"error": msg, "limit_exceeded": True}, ensure_ascii=False)
        if guard_state.check_dedup(name, kwargs):
            return json.dumps({"error": "检测到重复调用，已跳过", "dedup_skipped": True}, ensure_ascii=False)
        if requires_approval and not guard_state.approved:
            return json.dumps({"error": "此操作需要老师确认，请先调用 request_approval",
                               "requires_approval_blocked": True}, ensure_ascii=False)
        result = await fn(**kwargs)
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if isinstance(data, dict):
                    if "_route" in data:
                        guard_state.last_route = data.pop("_route")
                    if "_component" in data:
                        guard_state.last_component = data.pop("_component")
                    return json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(result, dict):
            if "_route" in result:
                guard_state.last_route = result.pop("_route")
            if "_component" in result:
                guard_state.last_component = result.pop("_component")
        return result

    return StructuredTool(name=base_tool.name, description=base_tool.description,
                          args_schema=base_tool.args_schema, coroutine=_guarded)


def _make_request_approval_tool(guard_state: GuardState):
    """Create a request_approval tool that triggers LangGraph interrupt()."""
    from langchain_core.tools import tool as lc_tool
    from langgraph.types import interrupt

    @lc_tool
    async def request_approval(message: str, context: str = "") -> str:
        """向老师请求确认。"""
        guard_state.approved = True
        interrupt({"type": "approval", "message": message, "context": context})
        return "approved"
    return request_approval


# ═══════════════════════════════════════════════════════════════════════
# Checkpointer (shared SqliteSaver singleton)
# ═══════════════════════════════════════════════════════════════════════

import aiosqlite as _aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_checkpointer = None


async def _get_checkpointer():
    """Return the shared AsyncSqliteSaver singleton for agent conversation persistence."""
    global _checkpointer
    if _checkpointer is None:
        conn = await _aiosqlite.connect("chemai_checkpoints.db")
        _checkpointer = AsyncSqliteSaver(conn)
        await _checkpointer.setup()
    return _checkpointer


# ═══════════════════════════════════════════════════════════════════════
# LLM Model Factory
# ═══════════════════════════════════════════════════════════════════════

def get_langchain_model(provider: str):
    """Return a ChatOpenAI model for the given provider (deepseek/mimo/zhipu/dashscope)."""
    from langchain_openai import ChatOpenAI
    from app.config import config as _cfg

    api_keys = _cfg.provider_keys
    configs = {
        "deepseek": {"model": _cfg.DEEPSEEK_MODEL, "base_url": _cfg.DEEPSEEK_BASE_URL},
        "mimo": {"model": _cfg.MIMO_MODEL, "base_url": _cfg.MIMO_BASE_URL},
        "zhipu": {"model": _cfg.ZHIPU_MODEL, "base_url": "https://open.bigmodel.cn/api/paas/v4"},
        "dashscope": {"model": _cfg.DASHSCOPE_MODEL, "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    }
    cfg = configs.get(provider, configs["deepseek"])
    return ChatOpenAI(model=cfg["model"], api_key=api_keys.get(provider, ""),
                      base_url=cfg["base_url"], temperature=0.3, max_tokens=4096)
