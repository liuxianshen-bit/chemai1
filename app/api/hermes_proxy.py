"""
化学问答代理 — 转发到 ChemAgent (DeepSeek)
"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ChemistryChatRequest(BaseModel):
    message: str
    history: Optional[list] = []


@router.post("/chemistry-chat")
async def chemistry_chat(request: ChemistryChatRequest):
    """AI 化学问答（流式），转发到 ChemAgent"""
    import sys, os
    from dotenv import load_dotenv
    load_dotenv()
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from agent.core import ChemAgent, AgentConfig
    import agent.skills.balance
    import agent.skills.search
    import agent.skills.diagnose
    import agent.skills.generate
    import agent.skills.tutor
    import agent.skills.experiment
    import agent.skills.weekly_report
    import agent.skills.import_exam
    import agent.skills.practice
    import agent.skills.web_search

    agent = ChemAgent(AgentConfig(persona="tutor"))

    async def generate():
        try:
            async for chunk in agent.run_stream(request.message, request.history):
                yield f"data: {chunk}\n\n"
                # 强制刷新缓冲区 — 用注释帧做心跳
                yield ": heartbeat\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            await agent.close()

    return StreamingResponse(generate(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@router.get("/health")
async def health_check():
    return {"status": "ok", "backend": "ChemAgent"}
