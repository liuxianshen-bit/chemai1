"""
ChemAgent FastAPI Channel — /api/agent/chat 端点（pydantic-ai 1.107.0）
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# ── 会话持久化（进程内存，重启丢失）──
_conversations: dict[str, dict] = {}


class ChatRequest(BaseModel):
    persona: str = "tutor"
    message: str
    student_id: Optional[str] = None
    provider: str = "deepseek"
    history: Optional[list[dict]] = None
    conversation_id: Optional[str] = None


@router.post("/chat")
async def agent_chat(request: ChatRequest):
    """非流式对话 — pydantic-ai Agent"""
    import os, sys
    from dotenv import load_dotenv

    load_dotenv()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from agent.agents import factory
    from agent.deps import ChemAIDeps
    from agent.memory import MemoryStack

    cid = request.conversation_id

    if cid and cid in _conversations:
        session = _conversations[cid]
        message_history = session.get("message_history")
        student_id = session.get("student_id") or request.student_id
    else:
        message_history = None
        student_id = request.student_id
        if cid:
            _conversations[cid] = {"message_history": [], "student_id": student_id}

    deps = ChemAIDeps(
        student_id=student_id,
        persona=request.persona,
        provider_name=request.provider,
    )

    if student_id:
        mem = MemoryStack()
        mem.load_student(student_id)
        deps.student_profile = mem.student_profile

    agent = factory.create_agent(
        persona=request.persona,
        provider=request.provider,
        deps=deps,
        user_message=request.message,
    )

    try:
        result = await agent.run(request.message, message_history=message_history)
        return {"content": result.output, "tokens_used": result.usage.get("total_tokens", 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    """流式对话（SSE），pydantic-ai 1.107.0"""
    import os, sys
    from dotenv import load_dotenv

    load_dotenv()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from agent.agents import factory
    from agent.deps import ChemAIDeps
    from agent.sse_adapter import SSEAdapter
    from agent.memory import MemoryStack
    from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart

    cid = request.conversation_id

    session = None
    message_history = None
    student_id = request.student_id

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

    agent = factory.create_agent(
        persona=request.persona,
        provider=request.provider,
        deps=deps,
        user_message=request.message,
    )

    adapter = SSEAdapter()
    full_reply = []

    async def generate():
        nonlocal full_reply
        try:
            yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

            async with agent.run_stream_events(
                request.message,
                deps=deps,
                message_history=message_history,
            ) as stream:
                async for event in stream:
                    for result in adapter.feed(event):
                        try:
                            evt = json.loads(result)
                            if evt.get("type") == "text":
                                full_reply.append(evt.get("content", ""))
                        except (json.JSONDecodeError, TypeError):
                            pass
                        yield f"data: {result}\n\n"

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

            if session is not None:
                if not message_history:
                    message_history = []
                message_history.append(ModelRequest(parts=[TextPart(content=request.message)]))
                message_history.append(ModelResponse(parts=[TextPart(content="".join(full_reply))]))
                session["message_history"] = message_history
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/reset")
async def reset_conversation(conversation_id: str):
    """重置对话记忆"""
    if conversation_id in _conversations:
        del _conversations[conversation_id]
        return {"success": True, "message": "对话已重置"}
    return {"success": False, "message": "对话不存在"}
