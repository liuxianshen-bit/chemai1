"""ChemAI LangGraph Channel — /api/agent/chat/langgraph 端点.

ReAct agent + interrupt/resume + SSE 兼容。
"""
import json, logging, os, sys
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_app_store():
    """Get the SqliteStore singleton from app.main."""
    try:
        from app.main import get_store
        return await get_store()
    except Exception:
        return None

# ── 复用 ChatRequest ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from agent.channel.fastapi_sse import (
    ChatRequest, _classify_and_narrow, _extract_conversation_context
)
from agent.memory import MemoryStack


_agent_cache: dict[str, object] = {}


async def _get_or_create_agent(persona: str = "tutor", provider: str = "deepseek",
                        student_profile=None, intent_hints="", version: str = "v1",
                        store=None):
    """Get or create agent. Returns (graph, guard_state, adapter_class)."""
    if version == "v2":
        from agent.langgraph_agent_v2 import create_chemai_agent as create_v2
        from agent.langgraph_sse_v2 import LangGraphSSEAdapterV2
        agent, guard = await create_v2(
            persona=persona, provider=provider,
            student_profile=student_profile, intent_hints=intent_hints,
            store=store,
        )
        return agent, guard, LangGraphSSEAdapterV2

    # v1: multi-agent
    from agent.langgraph_agent import create_chemai_agent
    from agent.langgraph_sse import LangGraphSSEAdapter

    agent, _ = await create_chemai_agent(
        persona=persona, provider=provider,
        student_profile=student_profile, intent_hints=intent_hints,
    )
    return agent, None, LangGraphSSEAdapter


@router.post("/chat/langgraph/stream")
async def agent_chat_langgraph_stream(request: ChatRequest):
    """流式对话 (SSE) — LangGraph ReAct agent + interrupt/resume."""
    from dotenv import load_dotenv
    load_dotenv()

    from agent.deps import ChemAIDeps
    from langgraph.errors import GraphInterrupt

    cid = request.conversation_id
    student_id = request.student_id

    # Session handling — only track student_id, no message_history
    from agent.channel.fastapi_sse import _conversations
    if cid and cid in _conversations:
        if not student_id:
            student_id = _conversations[cid].get("student_id")
    elif cid:
        _conversations[cid] = {"student_id": student_id}

    deps = ChemAIDeps(
        student_id=student_id,
        persona=request.persona,
        provider_name=request.provider,
    )

    if student_id:
        mem = MemoryStack()
        mem.load_student(student_id)
        deps.student_profile = mem.student_profile

    # Gateway classifier (no pydantic_ai message_history needed)
    tool_names, intent = await _classify_and_narrow(
        request.message, request.persona, None
    )

    # navigate shortcut
    if intent and intent.type == "navigate" and intent.page:
        async def _nav_gen():
            yield f"data: {json.dumps({'type': 'navigate', 'page': intent.page, 'params': {}}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(_nav_gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # Phase 3: extract pre-routed agent from Gateway classifier
    pre_routed_agent = None
    suggested_tools = None
    if intent and intent.target_agent and intent.confidence == "high":
        pre_routed_agent = intent.target_agent
        suggested_tools = intent.tools

    # Build hints for sub-agent (used regardless of routing)
    hints = ""
    if tool_names:
        hints = f"推荐工具: {', '.join(tool_names[:5])}\n用户消息: {request.message}\n使用推荐工具或其他工具，自行判断。"

    store = await _get_app_store()
    agent, guard_state, AdapterClass = await _get_or_create_agent(
        request.persona, request.provider,
        student_profile=deps.student_profile, intent_hints=hints,
        version=request.version, store=store,
    )

    adapter = AdapterClass()
    full_reply = []
    config = {"configurable": {"thread_id": cid or "default"}, "recursion_limit": 12}

    # Smart context management: TrimMessages + LLM summarization
    from agent.context_manager import trim_context
    await trim_context(agent, config)

    async def generate():
        nonlocal full_reply
        try:
            yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

            try:
                async for event in agent.astream_events(
                    {"messages": [{"role": "user", "content": request.message}],
                     "pre_routed_agent": pre_routed_agent,
                     "suggested_tools": suggested_tools or []},
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

            # Finalize: use guard_state for v2, graph state for v1
            final_state = await agent.aget_state(config)
            state_values = final_state.values if final_state else {}
            gs = guard_state
            for result in adapter.finalize(
                route=state_values.get("last_route") or (gs.last_route if gs else None),
                component=state_values.get("last_component") or (gs.last_component if gs else None),
                result_text=state_values.get("last_result_text"),
            ):
                if result == "[DONE]":
                    yield "data: [DONE]\n\n"
                else:
                    yield f"data: {result}\n\n"

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

    # Phase 3: pre-routed agent from Gateway
    pre_routed_agent2 = None
    suggested_tools2 = None
    if intent and intent.target_agent and intent.confidence == "high":
        pre_routed_agent2 = intent.target_agent
        suggested_tools2 = intent.tools

    store2 = await _get_app_store()
    agent, guard_state2, AdapterClass = await _get_or_create_agent(
        request.persona, request.provider,
        student_profile=deps.student_profile, intent_hints=hints,
        version=request.version, store=store2,
    )

    config = {"configurable": {"thread_id": cid or "default"}, "recursion_limit": 12}
    adapter = AdapterClass()

    from agent.context_manager import trim_context
    await trim_context(agent, config)

    try:
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": request.message}],
             "pre_routed_agent": pre_routed_agent2,
             "suggested_tools": suggested_tools2 or []},
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

    # Route from graph state (v1) or guard_state (v2)
    final_state = await agent.aget_state(config)
    state_values = final_state.values if final_state else {}
    response = {"content": text}
    last_route = state_values.get("last_route") if state_values else None
    last_component = state_values.get("last_component") if state_values else None
    if not last_route and guard_state2:
        last_route = guard_state2.last_route
    if not last_component and guard_state2:
        last_component = guard_state2.last_component
    if last_route and last_route.get("navigate"):
        route = last_route
        response["navigate"] = {"page": route.get("page"), "params": route.get("params", {})}
        if route.get("populate"):
            response.setdefault("populate", []).append(route["populate"])
        for act in route.get("actions", []):
            response.setdefault("actions", []).append(act)
    if last_component:
        response["component"] = last_component

    return response


@router.post("/chat/langgraph/resume")
async def agent_chat_langgraph_resume(request: ChatRequest):
    """中断恢复 — 发送 Command(resume=...) 继续被 interrupt 暂停的 graph。"""
    from dotenv import load_dotenv
    load_dotenv()

    from langgraph.types import Command
    from langgraph.errors import GraphInterrupt

    cid = request.conversation_id or "default"
    user_response = request.message or ""

    store3 = await _get_app_store()
    agent, guard_state, AdapterClass = await _get_or_create_agent(
        request.persona, request.provider, version=request.version, store=store3)
    adapter = AdapterClass()
    config = {"configurable": {"thread_id": cid}, "recursion_limit": 12}

    from agent.context_manager import trim_context
    await trim_context(agent, config)

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

            final_state = await agent.aget_state(config)
            state_values = final_state.values if final_state else {}
            gs = guard_state
            for result in adapter.finalize(
                route=state_values.get("last_route") or (gs.last_route if gs else None),
                component=state_values.get("last_component") or (gs.last_component if gs else None),
                result_text=state_values.get("last_result_text"),
            ):
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
    """重置对话 — 删除 _conversations 条目 + 清空 LangGraph checkpoint。"""
    from agent.channel.fastapi_sse import _conversations

    cleared_conv = False
    if conversation_id in _conversations:
        del _conversations[conversation_id]
        cleared_conv = True

    # Clear LangGraph checkpoint state
    try:
        from agent.langgraph_agent import _get_checkpointer
        cp = await _get_checkpointer()
        config = {"configurable": {"thread_id": conversation_id}}
        await cp.aput(config, checkpoint={"messages": []}, metadata={}, new_versions={})
    except Exception:
        pass

    if cleared_conv:
        return {"success": True, "message": "对话已重置"}
    return {"success": False, "message": "对话不存在"}


# ═══════════════════════════════════════════════════════════════════
# Agent 文件上传
# ═══════════════════════════════════════════════════════════════════

import uuid as _uuid
from fastapi import UploadFile, File, HTTPException

ALLOWED_MIMES = {
    "image/jpeg", "image/png", "image/bmp", "image/webp", "image/gif",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload")
async def agent_upload(file: UploadFile = File(...)):
    """Agent 对话中上传文件 → 预览 → 返回操作建议"""
    from dotenv import load_dotenv; load_dotenv()
    mime = file.content_type or ""
    if mime not in ALLOWED_MIMES:
        if not (file.filename or "").lower().endswith(('.doc', '.docx', '.pdf', '.png', '.jpg', '.jpeg')):
            raise HTTPException(400, f"不支持的文件格式: {mime}")

    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(400, "文件超过 10MB 限制")

    # Save session
    from app.models.database import get_db, UploadSession
    session_id = _uuid.uuid4().hex[:16]
    db = next(get_db())
    try:
        db.add(UploadSession(
            id=session_id,
            file_data=file_data,
            file_name=file.filename or "unknown",
            mime_type=mime,
            status="previewing",
        ))
        db.commit()
    finally:
        db.close()

    # Preview
    from app.services.ocr_service import ocr_service
    import logging as _log
    _log.getLogger(__name__).info(f'agent_upload: mime={mime}, size={len(file_data)}, fn={file.filename}')
    result = await ocr_service.recognize(file_data, mime)

    # Update session
    db = next(get_db())
    try:
        from sqlalchemy import update as sql_update
        db.execute(
            sql_update(UploadSession)
            .where(UploadSession.id == session_id)
            .values(
                status="ready",
                preview_text=result.get("preview_text", ""),
                formula_result=json.dumps(result.get("formula_result", []), ensure_ascii=False),
            )
        )
        db.commit()
    finally:
        db.close()

    preview_text = (result.get("preview_text", "") or "")
    if not preview_text and not result.get("success"):
        err = result.get("error", "unknown")
        logger.warning("agent_upload OCR failed: %s", err)
    return {
        "upload_id": session_id,
        "file_name": file.filename or "unknown",
        "preview_text": preview_text[:500] if preview_text else "",
        "error": result.get("error") if not result.get("success") else None,
        "actions": [
            {"id": "import", "label": "导入题库"},
            {"id": "grade", "label": "批改判卷"},
            {"id": "search", "label": "搜题解析"},
        ],
    }
