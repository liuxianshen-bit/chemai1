"""ChemAI LangGraph Channel — /api/agent/chat/langgraph 端点.

ReAct agent + interrupt/resume + SSE 兼容。
"""
import asyncio, json, logging, os, sys
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 复用 ChatRequest ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent.channel.fastapi_sse import (
    ChatRequest, _classify_and_narrow, _extract_conversation_context
)
from agent.memory import MemoryStack


# ── LangGraph agent 缓存 (per persona) ──
# ── Pre-flight gate ──

EXAM_INTENT_TRIGGERS = ["出题", "出卷", "组卷", "变种题", "真题", "高考题", "题目", "生成题", "出几道", "来几道"]
KP_INDICATORS = ["氧化还原", "电化学", "有机", "无机", "化学平衡", "盐类水解", "元素周期", "物质结构",
    "化学反应", "离子反应", "配平", "计算", "实验", "工业流程", "阿伏加德罗", "勒夏特列",
    "电解质", "水解", "电离", "原电池", "电解池", "晶体", "分子", "原子", "摩尔",
    "方程式", "同分异构", "官能团", "取代", "加成", "消去", "酯化", "聚合"]

def _preflight_check(message: str) -> str | None:
    """Check if user message is specific enough for tool calling.
    Returns clarifying questions if too vague, None if OK to proceed."""
    msg = message.strip()
    if len(msg) <= 4 and any(kw in msg for kw in ["你好", "在吗", "hi", "hello", "ping"]):
        return None
    has_exam = any(t in msg for t in EXAM_INTENT_TRIGGERS)
    if not has_exam:
        return None
    has_kp = any(kp in msg for kp in KP_INDICATORS)
    has_qty = any(c in msg for c in "123456789") or any(w in msg for w in ["几道", "几题", "一道", "两道", "三道"])
    has_diff = any(d in msg for d in ["简单", "中等", "困难", "基础", "中档", "综合"])
    has_type = any(t in msg for t in ["选择题", "填空题", "计算题", "实验题", "推断题"])
    if sum([has_kp, has_qty, has_diff, has_type]) >= 2:
        return None
    return (
        "我先确认一下你的需求，以便准确为你出题：\n\n"
        "**请告诉我以下信息：**\n"
        "1. **知识点板块** — 氧化还原、电化学、有机化学、化学平衡、元素周期律...\n"
        "2. **题型** — 选择题、填空题、计算题、实验题、推断题？\n"
        "3. **难度** — 基础、中等、困难？\n"
        "4. **数量** — 需要几道题？\n"
        "5. **是否有参考真题** — 需要基于哪一年的高考真题出变种题？\n\n"
        "可以直接说，比如：*\"氧化还原，选择题和填空题，中等难度，5道，参考2024年全国卷\"*"
    )


_agent_cache: dict[str, object] = {}


def _get_or_create_agent(persona: str, provider: str, student_profile=None, intent_hints=""):
    """Get or create agent for persona. Cache by persona key (interrupt-safe)."""
    from agent.langgraph_agent import create_chemai_agent

    # Each request gets a fresh guard_state — see D8/D9 guardrails
    agent, gs = create_chemai_agent(
        persona=persona, provider=provider,
        student_profile=student_profile, intent_hints=intent_hints,
    )
    return agent, gs


@router.post("/chat/langgraph/stream")
async def agent_chat_langgraph_stream(request: ChatRequest):
    """流式对话 (SSE) — LangGraph ReAct agent + interrupt/resume."""
    from dotenv import load_dotenv
    load_dotenv()

    from agent.deps import ChemAIDeps
    from agent.langgraph_sse import LangGraphSSEAdapter
    from langgraph.errors import GraphInterrupt
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart

    cid = request.conversation_id
    message_history = None
    student_id = request.student_id

    # Session handling
    from agent.channel.fastapi_sse import _conversations
    session = None
    if cid and cid in _conversations:
        session = _conversations[cid]
        message_history = session.get("message_history")
        if not student_id:
            student_id = session.get("student_id")
    elif cid:
        session = {"message_history": [], "student_id": student_id}
        _conversations[cid] = session

    deps = ChemAIDeps(
        student_id=student_id,
        persona=request.persona,
        provider_name=request.provider,
    )

    if student_id:
        mem = MemoryStack()
        mem.load_student(student_id)
        deps.student_profile = mem.student_profile

    # Gateway classifier
    tool_names, intent = await _classify_and_narrow(
        request.message, request.persona, message_history
    )

    # navigate shortcut
    if intent and intent.type == "navigate" and intent.page:
        async def _nav_gen():
            yield f"data: {json.dumps({'type': 'navigate', 'page': intent.page, 'params': {}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_nav_gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # Build hints from classifier
    hints = ""
    if tool_names:
        hints = f"推荐工具: {', '.join(tool_names[:5])}\n用户消息: {request.message}\n使用推荐工具或其他工具，自行判断。"

    agent, guard_state = _get_or_create_agent(
        request.persona, request.provider,
        student_profile=deps.student_profile, intent_hints=hints,
    )

    adapter = LangGraphSSEAdapter()
    full_reply = []
    config = {"configurable": {"thread_id": cid or "default"}, "recursion_limit": 8}

    async def generate():
        nonlocal full_reply, message_history
        try:
            yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

            try:
                async for event in agent.astream_events(
                    {"messages": [{"role": "user", "content": request.message}]},
                    config,
                    version="v2",
                ):
                    for result in adapter.feed(event):
                        try:
                            evt = json.loads(result)
                            if evt.get("type") == "text":
                                full_reply.append(evt.get("content", ""))
                        except (json.JSONDecodeError, TypeError):
                            pass
                        yield f"data: {result}\n\n"

            except GraphInterrupt:
                # Interrupt detected via exception — graph paused, waiting for resume
                yield f"data: {json.dumps({'type': 'phase', 'phase': 'awaiting_approval'}, ensure_ascii=False)}\n\n"
                return

            # Check for interrupt via state inspection (backup path)
            state = agent.get_state(config)
            if state and state.next and "__interrupt__" in str(state.next):
                yield f"data: {json.dumps({'type': 'phase', 'phase': 'awaiting_approval'}, ensure_ascii=False)}\n\n"
                return

            # Finalize: route events + done (uses guard_state.last_route)
            for result in adapter.finalize(route=guard_state.last_route, component=guard_state.last_component):
                if result == "[DONE]":
                    yield "data: [DONE]\n\n"
                else:
                    yield f"data: {result}\n\n"

            if session is not None:
                if not message_history:
                    message_history = []
                message_history.append(ModelRequest(parts=[TextPart(content=request.message)]))
                message_history.append(ModelResponse(parts=[TextPart(content="".join(full_reply))]))
                session["message_history"] = message_history

        except Exception as e:
            import traceback; traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/chat/langgraph")
async def agent_chat_langgraph(request: ChatRequest):
    """非流式对话 — LangGraph ReAct agent。"""
    from dotenv import load_dotenv
    load_dotenv()

    from agent.deps import ChemAIDeps
    from agent.langgraph_sse import LangGraphSSEAdapter
    from langgraph.errors import GraphInterrupt

    cid = request.conversation_id
    student_id = request.student_id

    deps = ChemAIDeps(persona=request.persona, provider_name=request.provider)
    if student_id:
        mem = MemoryStack()
        mem.load_student(student_id)
        deps.student_profile = mem.student_profile

    tool_names, intent = await _classify_and_narrow(
        request.message, request.persona, None
    )

    if intent and intent.type == "navigate" and intent.page:
        return {"content": "", "navigate": {"page": intent.page, "params": {}}}

    hints = ""
    if tool_names:
        hints = f"推荐工具: {', '.join(tool_names[:5])}\n用户消息: {request.message}\n使用推荐工具或其他工具，自行判断。"

    agent, guard_state = _get_or_create_agent(
        request.persona, request.provider,
        student_profile=deps.student_profile, intent_hints=hints,
    )

    config = {"configurable": {"thread_id": cid or "default"}, "recursion_limit": 8}
    adapter = LangGraphSSEAdapter()

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": request.message}]},
            config,
        )
    except GraphInterrupt:
        return {"content": "", "interrupt": True, "message": "Agent waiting for approval"}

    # Extract final text
    msgs = result.get("messages", [])
    text = ""
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        if content and isinstance(content, str) and content.strip():
            text = content
            break

    # Route from guard_state (not from tool results — _route is stripped there)
    response = {"content": text}
    if guard_state.last_route and guard_state.last_route.get("navigate"):
        route = guard_state.last_route
        response["navigate"] = {"page": route.get("page"), "params": route.get("params", {})}
        if route.get("populate"):
            response.setdefault("populate", []).append(route["populate"])
        for act in route.get("actions", []):
            response.setdefault("actions", []).append(act)

    return response


@router.post("/chat/langgraph/resume")
async def agent_chat_langgraph_resume(request: ChatRequest):
    """中断恢复 — 发送 Command(resume=...) 继续被 interrupt 暂停的 graph。"""
    from dotenv import load_dotenv
    load_dotenv()

    from agent.langgraph_sse import LangGraphSSEAdapter
    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt

    cid = request.conversation_id or "default"
    user_response = request.message or ""

    agent, guard_state = _get_or_create_agent(request.persona, request.provider)
    adapter = LangGraphSSEAdapter()
    config = {"configurable": {"thread_id": cid}, "recursion_limit": 8}
    full_reply = []

    async def generate():
        nonlocal full_reply
        try:
            try:
                async for event in agent.astream_events(
                    Command(resume=user_response),
                    config,
                    version="v2",
                ):
                    for result in adapter.feed(event):
                        try:
                            evt = json.loads(result)
                            if evt.get("type") == "text":
                                full_reply.append(evt.get("content", ""))
                        except (json.JSONDecodeError, TypeError):
                            pass
                        yield f"data: {result}\n\n"

            except GraphInterrupt:
                yield f"data: {json.dumps({'type': 'phase', 'phase': 'awaiting_approval'}, ensure_ascii=False)}\n\n"
                return

            for result in adapter.finalize(route=guard_state.last_route, component=guard_state.last_component):
                if result == "[DONE]":
                    yield "data: [DONE]\n\n"
                else:
                    yield f"data: {result}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/chat/langgraph/reset")
async def agent_chat_langgraph_reset(conversation_id: str):
    """重置对话 — 删除 thread checkpoint。"""
    from agent.channel.fastapi_sse import _conversations

    if conversation_id in _conversations:
        del _conversations[conversation_id]
        return {"success": True, "message": "对话已重置"}
    return {"success": False, "message": "对话不存在"}
