"""
ChemAgent FastAPI Channel — /api/agent/chat 端点（pydantic-ai 1.107.0）

v3: 两分类 Gateway (chat/navigate) + tool 自路由 (_route)
"""
import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

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


def _extract_conversation_context(message_history: list | None, max_turns: int = 2) -> str:
    """Extract the last N turns from pydantic-ai message_history as text context."""
    if not message_history:
        return ""

    from pydantic_ai.messages import ModelRequest, ModelResponse

    lines = []
    recent = message_history[-max_turns * 2:]  # each turn = request + response
    for msg in recent:
        if isinstance(msg, ModelRequest):
            text = next((p.content for p in msg.parts if hasattr(p, 'content') and p.content), "")
            if text:
                lines.append(f"用户: {text[:200]}")
        elif isinstance(msg, ModelResponse):
            text = next((p.content for p in msg.parts if hasattr(p, 'content') and p.content), "")
            if text:
                lines.append(f"助手: {text[:200]}")

    return "\n".join(lines) if lines else ""


async def _classify_and_narrow(
    message: str,
    persona: str,
    message_history: list | None,
) -> tuple[list[str] | None, object | None]:
    """Run the Gateway LLM classifier. Returns (tool_names, intent_result_or_None).

    Returns (None, None) if classification fails — caller should use all tools.
    """
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

    try:
        from agent.agents import load_persona
        from agent.gateway import IntentClassifier
        from agent.provider.deepseek import get_classifier_provider

        persona_config = load_persona(persona)
        available_skills = persona_config.get("available_skills", [])
        conversation_context = _extract_conversation_context(message_history)

        provider = get_classifier_provider()
        classifier = IntentClassifier(provider)

        result = await asyncio.wait_for(
            classifier.classify(
                message,
                available_skills=available_skills,
                conversation_context=conversation_context,
            ),
            timeout=5.0,
        )
        return result.tools, result

    except asyncio.TimeoutError:
        logger.warning("IntentClassifier: timed out after 5s, falling back to all tools")
        return None, None
    except Exception:
        logger.warning("IntentClassifier: classification failed", exc_info=True)
        return None, None


def _extract_tool_results(agent_result) -> list[dict]:
    """Extract tool call results from pydantic-ai AgentRunResult."""
    results = []
    for msg in agent_result.all_messages():
        for part in getattr(msg, 'parts', []):
            tool_name = getattr(part, 'tool_name', None)
            if tool_name and hasattr(part, 'content'):
                content = part.content
                try:
                    if isinstance(content, str):
                        data = json.loads(content)
                    else:
                        data = content
                except (json.JSONDecodeError, TypeError):
                    data = {"raw": str(content)[:500]}
                results.append({"tool_name": tool_name, "result": data})
    return results


def _extract_route_events(tool_results: list[dict]) -> dict:
    """Read _route from tool results and build navigate/populate/action events.

    Returns {"navigate": {...}|None, "populates": [...], "actions": [...]}
    Only the first tool with _route.navigate=True triggers navigation.
    """
    for tr in tool_results:
        route = tr.get("result", {}).get("_route")
        if route and route.get("navigate"):
            return {
                "navigate": {"page": route.get("page"), "params": {}},
                "populates": [route["populate"]] if route.get("populate") else [],
                "actions": route.get("actions", []),
            }
    return {"navigate": None, "populates": [], "actions": []}


@router.post("/chat")
async def agent_chat(request: ChatRequest):
    """非流式对话 — pydantic-ai Agent（Gateway 两分类 + tool 自路由）"""
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

    # Phase 1: Gateway LLM classifier
    tool_names, intent = await _classify_and_narrow(
        request.message, request.persona, message_history
    )

    # navigate type: direct page open, no Agent
    if intent and intent.type == "navigate" and intent.page:
        return {
            "content": "",
            "navigate": {"page": intent.page, "params": {}},
        }

    # Phase 2: Create agent with narrowed tools
    agent = factory.create_agent(
        persona=request.persona,
        provider=request.provider,
        deps=deps,
        tool_names=tool_names,
    )

    try:
        result = await agent.run(request.message, message_history=message_history)
        response = {"content": result.output, "tokens_used": result.usage.get("total_tokens", 0)}

        # Phase 3: Read _route from tool results
        if intent and intent.type == "chat":
            tool_results = _extract_tool_results(result)
            nav = _extract_route_events(tool_results)
            if nav["navigate"]:
                response["navigate"] = nav["navigate"]
                if nav["populates"]:
                    response["populate"] = nav["populates"]
                if nav["actions"]:
                    response["actions"] = nav["actions"]

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    """流式对话（SSE），pydantic-ai 1.107.0 + Gateway 两分类 + tool 自路由"""
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

    # Phase 1: Gateway LLM classifier
    tool_names, intent = await _classify_and_narrow(
        request.message, request.persona, message_history
    )

    adapter = SSEAdapter()
    full_reply = []
    tool_results = []  # collected from stream events

    async def generate():
        nonlocal full_reply, tool_results, message_history
        try:
            # navigate type: direct page open, no Agent
            if intent and intent.type == "navigate" and intent.page:
                yield f"data: {json.dumps({'type': 'navigate', 'page': intent.page, 'params': {}}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

            # Phase 2: Create agent with narrowed tools
            agent = factory.create_agent(
                persona=request.persona,
                provider=request.provider,
                deps=deps,
                tool_names=tool_names,
            )

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
                            elif evt.get("type") == "tool_result":
                                raw_result = evt.get("result", {})
                                if isinstance(raw_result, str):
                                    try:
                                        raw_result = json.loads(raw_result)
                                    except (json.JSONDecodeError, TypeError):
                                        raw_result = {"raw": raw_result[:500]}
                                tool_results.append({
                                    "tool_name": evt.get("name", "unknown"),
                                    "result": raw_result,
                                })
                        except (json.JSONDecodeError, TypeError):
                            pass
                        yield f"data: {result}\n\n"

            # Phase 3: Read _route from tool results, emit navigation events
            nav = _extract_route_events(tool_results)
            if nav["navigate"]:
                yield f"data: {json.dumps({'type': 'navigate', 'page': nav['navigate']['page'], 'params': nav['navigate']['params']}, ensure_ascii=False)}\n\n"
            for pop in nav["populates"]:
                yield f"data: {json.dumps({'type': 'populate', 'target': pop['target'], 'data': pop['data']}, ensure_ascii=False)}\n\n"
            for act in nav["actions"]:
                yield f"data: {json.dumps({'type': 'action', 'action': act['action'], 'payload': act['payload']}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

            if session is not None:
                if not message_history:
                    message_history = []
                message_history.append(ModelRequest(parts=[TextPart(content=request.message)]))
                message_history.append(ModelResponse(parts=[TextPart(content="".join(full_reply))]))
                session["message_history"] = message_history
        except Exception as e:
            import traceback; traceback.print_exc()
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
