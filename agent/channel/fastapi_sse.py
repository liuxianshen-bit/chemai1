"""
ChemAgent FastAPI Channel — /api/agent/chat 端点
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ChatRequest(BaseModel):
    persona: str = "tutor"  # tutor / teacher / parent
    message: str
    student_id: Optional[str] = None
    provider: str = "deepseek"  # deepseek / zhipu / dashscope
    history: Optional[list[dict]] = None


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
    """流式对话（SSE）"""
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

    config = AgentConfig(
        persona=request.persona,
        provider=request.provider,
    )
    agent = ChemAgent(config)

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
