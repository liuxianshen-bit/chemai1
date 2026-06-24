"""ChemAI Multi-Agent StateGraph — Coordinator + Router + Sub-Agent architecture.

Replaces monolithic ReAct agent with coordinator/router + 6 domain sub-agents.
Each sub-agent is a StateGraph node with its own GuardState and 2-4 tools.

Graph: START → coordinator → routing_tools → router → [sub-agent] → coordinator → END
Routing tools execute through a real ToolNode — frontend sees tool_call/tool_result cards.
"""
import json, os, logging
from typing import Annotated
from uuid import uuid4
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

_checkpointer = MemorySaver()
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool as lc_tool, StructuredTool

logger = logging.getLogger(__name__)

TOOL_APPROVAL_REQUIRED = {"assign_adaptive_practice", "import_exam_paper", "delete_bank"}
RECURSION_LIMIT = 8

TOOL_CALL_LIMITS: dict[str, int] = {
    "search_exam_bank": 3, "web_search": 2, "show_exam_workbench": 3,
    "diagnose_barrier": 2, "weekly_report": 2, "balance_equation": 3,
    "chemistry_tutor": 3, "simulate_experiment": 2, "import_exam_paper": 1,
    "assign_adaptive_practice": 1, "save_to_bank": 1, "show_students": 1,
    "show_diagnosis": 1,
}


class GuardState:
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
        limit = TOOL_CALL_LIMITS.get(name)
        if limit is None:
            return None
        count = self.call_counts.get(name, 0) + 1
        self.call_counts[name] = count
        if count > limit:
            return f"已调用 {name} {count} 次（上限 {limit} 次），请基于已有结果继续。"
        return None

    def check_prerequisites(self, name: str, kwargs: dict) -> str | None:
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


def _make_guarded_tool(fn, guard_state: GuardState, requires_approval: bool = False):
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
    @lc_tool
    async def request_approval(message: str, context: str = "") -> str:
        """向老师请求确认。"""
        guard_state.approved = True
        interrupt({"type": "approval", "message": message, "context": context})
        return "approved"
    return request_approval


# ═══════════════════════════════════════════════════════════════════════
# Multi-Agent State
# ═══════════════════════════════════════════════════════════════════════

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent, ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage


class MultiAgentState(MessagesState):
    shared_context: dict
    route_decision: dict | None
    target_agent: str | None
    agent_query: str | None
    last_component: dict | None
    last_route: dict | None
    last_result_text: str | None
    reroute: str | None


# ═══════════════════════════════════════════════════════════════════════
# Sub-Agent Factory
# ═══════════════════════════════════════════════════════════════════════

_SUB_AGENT_OUTPUT_CONTRACT = """
输出格式：返回合法的 JSON 对象，至少包含 "result" 键。如果获取了学生/班级信息，在 JSON 顶层包含这些字段。
**严禁生成任何额外文字。** 工具调用完成后立即输出 JSON，不要加任何解释、问候、列表、建议。"""


def create_sub_agent_node(name: str, tool_names: list[str], system_prompt: str,
                          approval_tools: set[str] | None = None):
    from agent.tools import TOOLS
    from agent.browser_tools import (
        browse_navigate, browse_read, browse_click,
        browse_input, browse_screenshot,
    )
    if approval_tools is None:
        approval_tools = set()
    guard_state = GuardState()
    all_tools = list(TOOLS) + [browse_navigate, browse_read, browse_click,
                                browse_input, browse_screenshot]
    _tool_by_name = {t.__name__: t for t in all_tools}
    approval = set(approval_tools) & set(TOOL_APPROVAL_REQUIRED)
    tools = [_make_guarded_tool(_tool_by_name[tn], guard_state, tn in approval)
             for tn in tool_names if tn in _tool_by_name]
    tools.append(_make_request_approval_tool(guard_state))

    agent = create_react_agent(model=get_langchain_model("deepseek"), tools=tools,
                               name=name, prompt=system_prompt + "\n\n" + _SUB_AGENT_OUTPUT_CONTRACT)

    async def node_fn(state: MultiAgentState) -> dict:
        query = state.get("agent_query", "") or ""
        ctx = state.get("shared_context", {}) or {}
        full_query = f"[共享上下文]\n{json.dumps(ctx, ensure_ascii=False)}\n\n[用户请求]\n{query}" if ctx else query
        try:
            result = await agent.ainvoke(
                {"messages": [HumanMessage(content=full_query)]},
                {"configurable": {"thread_id": f"{name}-{uuid4()}"}, "recursion_limit": 7},
            )
            content = result["messages"][-1].content
            component = guard_state.last_component
            route = guard_state.last_route
            extracted_ctx = {}

            # Extract JSON from content — LLM may add trailing text after JSON
            import re as _re
            result_text = content
            reroute = None
            json_data = None
            _m = _re.search(r'\{[^{}]*"result"\s*:\s*"[^"]*"[^{}]*\}', str(content))
            if not _m:
                _m = _re.search(r'\{.*\}', str(content), _re.DOTALL)
            if _m:
                try:
                    json_data = json.loads(_m.group())
                except (json.JSONDecodeError, TypeError):
                    pass
            if json_data and isinstance(json_data, dict):
                reroute = json_data.get("reroute")
                result_text = json_data.get("result", result_text)
                for k in ("student_id", "student_name", "class_id", "class_name",
                           "barrier_type", "barrier_distribution"):
                    if k in json_data:
                        extracted_ctx[k] = json_data[k]

            return {
                "messages": [AIMessage(content=result_text)],
                "shared_context": {**ctx, **extracted_ctx},
                "last_component": component or (json_data or {}).get("_component"),
                "last_route": route or (json_data or {}).get("_route"),
                "last_result_text": result_text,
                "reroute": reroute,
            }
        except Exception as e:
            logger.error(f"[{name}] Sub-agent failed: {e}")
            return {"messages": [AIMessage(content=json.dumps(
                {"result": f"抱歉处理遇到问题: {str(e)[:200]}", "error": True},
                ensure_ascii=False))], "shared_context": ctx}
    return node_fn


_agent_node_cache: dict[str, callable] = {}

_SUB_AGENT_DEFS = {
    "search_expert": {
        "tools": ["search_exam_bank", "web_search"],
        "prompt": ("搜索专家。不闲聊，直接调工具。搜不到直接告知。"),
        "approval": set(),
    },
    "exam_expert": {
        "tools": ["show_exam_workbench", "save_to_bank"],
        "prompt": ("出题专家。你的唯一任务：立即调用 show_exam_workbench。"
                   "不要生成任何文字。不要反问用户。不要列出任何选项。"
                   "工具返回后立刻输出JSON结束。保存用 save_to_bank。"),
        "approval": set(),
    },
    "diagnosis_expert": {
        "tools": ["diagnose_barrier", "show_diagnosis", "show_students", "assign_adaptive_practice"],
        "prompt": ("诊断专家。不闲聊。直接调工具。\n"
                   "规则：\n"
                   "1. 消息包含具体学号(纯数字)或\"诊断学生 XXX\" → 调 diagnose_barrier(student_id=学号)\n"
                   "2. 用户问有哪些学生/找问题学生/班里谁薄弱 → 调 show_students，调完立即停止\n"
                   "3. 用户说班级名+学生(如\"高一一班的学生\") → 调 show_students\n"
                   "4. show_students 成功后不要再调任何工具，直接输出结果\n"
                   "5. assign_adaptive_practice 需先 request_approval"),
        "approval": {"assign_adaptive_practice"},
    },
    "tutor_expert": {
        "tools": ["chemistry_tutor", "simulate_experiment", "balance_equation", "weekly_report"],
        "prompt": ("辅导专家。禁止说\"好的\"\"我来\"\"让我\"等开场白。\n"
                   "配平: 收到方程式后只调 balance_equation，调完立即返回。\n"
                   "讲解/实验/报告: 调对应工具，简洁输出。"),
        "approval": set(),
    },
    "bank_manager": {
        "tools": ["list_banks", "delete_bank"],
        "prompt": ("题库管理。不闲聊。delete_bank 需先 request_approval。"),
        "approval": {"delete_bank"},
    },
    "browser_expert": {
        "tools": ["browse_navigate", "browse_read", "browse_click",
                  "browse_input", "browse_screenshot"],
        "prompt": ("浏览器专家。不闲聊。navigate→read→返回结果。超时直接告知。"),
        "approval": set(),
    },
}


def _get_or_compile_agent_node(name: str) -> callable:
    if name not in _agent_node_cache:
        cfg = _SUB_AGENT_DEFS[name]
        _agent_node_cache[name] = create_sub_agent_node(
            name, cfg["tools"], cfg["prompt"], cfg["approval"])
        logger.info(f"[MultiAgent] Compiled: {name}")
    return _agent_node_cache[name]


# ═══════════════════════════════════════════════════════════════════════
# Routing Tools — real ToolNode execution → frontend sees tool cards
# ═══════════════════════════════════════════════════════════════════════

_ROUTING_TOOLS = {}

def _make_routing_tool(agent_name: str, display: str):
    @lc_tool
    async def _route(query: str = "") -> str:
        """Route to expert."""
        return json.dumps({"agent": agent_name, "display": display, "query": query}, ensure_ascii=False)
    _route.name = f"route_to_{agent_name}"
    _route.description = f"将用户请求路由到{display}。"
    _ROUTING_TOOLS[_route.name] = agent_name
    return _route

_route_to_search_expert = _make_routing_tool("search_expert", "搜索专家")
_route_to_exam_expert = _make_routing_tool("exam_expert", "出题专家")
_route_to_diagnosis_expert = _make_routing_tool("diagnosis_expert", "诊断专家")
_route_to_tutor_expert = _make_routing_tool("tutor_expert", "辅导专家")
_route_to_bank_manager = _make_routing_tool("bank_manager", "题库管理")
_route_to_browser_expert = _make_routing_tool("browser_expert", "浏览器专家")

_ROUTING_TOOL_LIST = [
    _route_to_search_expert, _route_to_exam_expert, _route_to_diagnosis_expert,
    _route_to_tutor_expert, _route_to_bank_manager, _route_to_browser_expert,
]
_routing_tool_node = ToolNode(_ROUTING_TOOL_LIST)


# ═══════════════════════════════════════════════════════════════════════
# Coordinator + Router
# ═══════════════════════════════════════════════════════════════════════

_COORDINATOR_SYS_PROMPT = """你是 ChemAI 调度员。分析用户消息，调用路由工具。

**只调工具，不说话！** 不要在调用前生成任何文字。

[ROUTING]
查学生/班级/障碍/诊断/练习 → route_to_diagnosis_expert
搜索/查资料/真题 → route_to_search_expert
出题/组卷/保存/考试 → route_to_exam_expert
讲解/实验/配平/周报 → route_to_tutor_expert
题库管理/删除题库 → route_to_bank_manager
打开网页/看网站 → route_to_browser_expert

**班级名/学生名一律走 diagnosis_expert，和关键词无关。**
只有闲聊/打招呼时才不调工具直接回复。"""


def _coordinator_node(state: MultiAgentState) -> dict:
    msgs = list(state.get("messages", []))

    if state.get("reroute"):
        return {"route_decision": {"agent": state["reroute"], "query": ""}, "reroute": None}

    # Return from sub-agent？Skip text if component panel is the response
    if (len(msgs) >= 2 and isinstance(msgs[-1], AIMessage)
            and not getattr(msgs[-1], 'tool_calls', None)):
        last_component = state.get("last_component")
        if last_component:
            return {"route_decision": {"agent": "respond", "query": ""}, "messages": []}
        model = get_langchain_model("deepseek")
        ctx = state.get("shared_context", {})
        ctx_str = ""
        if ctx:
            ctx_str = "已知信息: " + json.dumps(ctx, ensure_ascii=False) + "\n"
        response = model.invoke(
            [SystemMessage(content=(
                "你是 ChemAI 高中化学助教。子Agent已经在面板中展示了完整结果，"
                "你只需要用1-2句话简要概括结论即可。"
                "绝对不要重复子Agent已经列出的内容（如知识点列表、步骤、选项等）。"
                "不要加\"好的\"\"我来\"等开场白。"
            ))] + msgs
        )
        return {"route_decision": {"agent": "respond", "query": ""}, "messages": [response]}

    model = get_langchain_model("deepseek")
    model_with_tools = model.bind_tools(_ROUTING_TOOL_LIST)
    response = model_with_tools.invoke([SystemMessage(content=_COORDINATOR_SYS_PROMPT)] + msgs)

    tc_list = getattr(response, 'tool_calls', []) or []
    if tc_list:
        tc = tc_list[0]
        agent_name = _ROUTING_TOOLS.get(tc.get("name", ""), "respond")
        # Strip coordinator's text chatter — keep only tool_calls in the message
        clean = AIMessage(content="", id=response.id)
        clean.tool_calls = response.tool_calls
        return {
            "route_decision": {"agent": agent_name, "query": tc.get("args", {}).get("query", "")},
            "messages": [clean],
        }
    return {"route_decision": {"agent": "respond", "query": ""}, "messages": [response]}


def _router_node(state: MultiAgentState) -> dict:
    decision = state.get("route_decision") or {}
    agent = decision.get("agent", "respond")
    if agent == "respond":
        return {"target_agent": None, "route_decision": None}

    # Extract query from routing tool's ToolMessage
    query = ""
    for m in reversed(state.get("messages", [])):
        if getattr(m, 'name', '') and (m.name or "").startswith('route_to_'):
            try:
                data = json.loads(m.content) if isinstance(m.content, str) else m.content
                query = data.get("query", "")
            except:
                pass
            break

    return {"target_agent": agent, "agent_query": query}


def _route_after_routing(state: MultiAgentState) -> str:
    # After routing tools: if tool calls were made → router. Otherwise END.
    last = state.get("messages", [None])[-1]
    if last and getattr(last, 'tool_calls', None):
        return "routing_tools"
    return "router"


def _route_after_router(state: MultiAgentState) -> str:
    return state.get("target_agent") or END


# ═══════════════════════════════════════════════════════════════════════
# Graph Assembly
# ═══════════════════════════════════════════════════════════════════════

def create_chemai_agent(persona: str = "tutor", provider: str = "deepseek",
                        student_profile=None, intent_hints="", guard_state=None):
    builder = StateGraph(MultiAgentState)

    builder.add_node("coordinator", _coordinator_node)
    builder.add_node("routing_tools", _routing_tool_node)
    builder.add_node("router", _router_node)
    for name in _SUB_AGENT_DEFS:
        builder.add_node(name, _get_or_compile_agent_node(name))

    builder.add_edge(START, "coordinator")
    builder.add_conditional_edges("coordinator", _route_after_routing, {
        "routing_tools": "routing_tools", "router": "router",
    })
    builder.add_edge("routing_tools", "router")

    builder.add_conditional_edges("router", _route_after_router, {
        name: name for name in _SUB_AGENT_DEFS
    } | {END: END})

    for name in _SUB_AGENT_DEFS:
        builder.add_edge(name, "coordinator")

    graph = builder.compile(checkpointer=_checkpointer)
    logger.info("[MultiAgent] Graph compiled — 6 sub-agents ready")
    return graph, None


# ═══════════════════════════════════════════════════════════════════════
# Shared utilities
# ═══════════════════════════════════════════════════════════════════════

def get_langchain_model(provider: str) -> ChatOpenAI:
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
    return ChatOpenAI(model=cfg["model"], api_key=api_keys.get(provider, ""),
                      base_url=cfg["base_url"], temperature=0.3, max_tokens=4096)
