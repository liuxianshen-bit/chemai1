"""
ChemAgent FastAPI Channel — /api/agent/chat 端点
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# ── 会话持久化（进程内存，重启丢失）──
_conversations: dict[str, "ChemAgent"] = {}  # type: ignore


class ChatRequest(BaseModel):
    persona: str = "tutor"  # tutor / teacher / parent
    message: str
    student_id: Optional[str] = None
    provider: str = "deepseek"  # deepseek / zhipu / dashscope
    history: Optional[list[dict]] = None
    conversation_id: Optional[str] = None  # 提供则复用已有 agent 记忆


@router.post("/chat")
async def agent_chat(request: ChatRequest):
    """非流式对话"""
    import os, sys
    from dotenv import load_dotenv

    load_dotenv()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from agent.core import ChemAgent, AgentConfig

    # 导入所有 skill（触发 @registry.register）
    import agent.skills.balance
    import agent.skills.search
    import agent.skills.diagnose
    import agent.skills.generate
    import agent.skills.tutor
    import agent.skills.experiment
    import agent.skills.weekly_report
    import agent.skills.import_exam
    import agent.skills.web_search
    import agent.skills.practice

    config = AgentConfig(
        persona=request.persona,
        provider=request.provider,
    )
    agent = ChemAgent(config)

    if request.student_id:
        agent.memory.load_student(request.student_id)

    try:
        result = await agent.run(request.message, request.history)
        await agent.close()
        return {
            "content": result.content,
            "action": result.action,
            "skill_calls": result.skill_calls,
            "tokens_used": result.tokens_used,
        }
    except Exception as e:
        await agent.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    """流式对话（SSE），支持 conversation_id 持久化"""
    import os, sys
    from dotenv import load_dotenv

    load_dotenv()

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from agent.core import ChemAgent, AgentConfig

    # 导入所有 skill
    import agent.skills.balance
    import agent.skills.search
    import agent.skills.diagnose
    import agent.skills.generate
    import agent.skills.tutor
    import agent.skills.experiment
    import agent.skills.weekly_report
    import agent.skills.import_exam
    import agent.skills.web_search
    import agent.skills.practice

    cid = request.conversation_id

    # 复用已有 agent 或创建新的
    if cid and cid in _conversations:
        agent = _conversations[cid]
    else:
        config = AgentConfig(
            persona=request.persona,
            provider=request.provider,
        )
        agent = ChemAgent(config)
        if cid:
            _conversations[cid] = agent

    if request.student_id:
        agent.memory.load_student(request.student_id)

    async def generate():
        try:
            async for chunk in agent.run_stream(request.message, request.history):
                yield f"data: {chunk}\n\n"
                yield ": heartbeat\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if not cid:
                await agent.close()

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
