"""
ChemAI PydanticAI 集成 — 1.107.0 版本
基于 pydantic-ai 1.107.0 的 DeepSeek agent + search_exam_bank tool + generate_questions tool
"""
import json
from typing import AsyncIterator
from dotenv import load_dotenv
from pydantic_ai import Agent

load_dotenv()


def create_search_agent():
    """创建带真题搜索工具的 PydanticAI agent"""
    from agent.skills.search_pydantic import search_exam_bank_plain

    agent = Agent(
        "deepseek:deepseek-chat",
        system_prompt=(
            "你是高中化学教研助手。当用户要求搜索真题时，调用 search_exam_bank 工具。"
            "用中文回复，结构清晰。"
        ),
    )

    @agent.tool_plain
    def search_exam_bank(
        keyword: str = "",
        year: int = 0,
        difficulty: str = "",
        limit: int = 5,
    ) -> str:
        """搜索历年高考化学真题"""
        result = search_exam_bank_plain(
            keyword=keyword,
            year=year if year else None,
            difficulty=difficulty or None,
            limit=limit,
        )
        return json.dumps(
            {"total": result.total, "questions": result.questions},
            ensure_ascii=False,
        )

    return agent


def create_chem_agent():
    """创建带搜索 + 出题双工具的 PydanticAI agent（Phase 0.5 使用）"""
    from agent.skills.search_pydantic import search_exam_bank_plain
    from agent.tools import generate_questions as generate_questions_pydantic

    agent = Agent(
        "deepseek:deepseek-chat",
        system_prompt=(
            "你是高中化学教研助手。你可以：\n"
            "1. 搜索历年高考真题（调用 search_exam_bank）\n"
            "2. 根据知识点生成练习题（调用 generate_questions）\n"
            "当用户要求出题时，调用 generate_questions 工具，然后用中文整理题目列表呈现。"
        ),
    )

    @agent.tool_plain
    def search_exam_bank(
        keyword: str = "",
        year: int = 0,
        difficulty: str = "",
        limit: int = 5,
    ) -> str:
        """搜索历年高考化学真题"""
        result = search_exam_bank_plain(
            keyword=keyword,
            year=year if year else None,
            difficulty=difficulty or None,
            limit=limit,
        )
        return json.dumps(
            {"total": result.total, "questions": result.questions},
            ensure_ascii=False,
        )

    @agent.tool_plain
    async def generate_questions(
        knowledge_points: str = "",
        difficulty: str = "medium",
        quantity: int = 5,
    ) -> str:
        """根据知识点和难度生成高中化学练习题。内部调用 LLM 出题，返回题目列表和审核结果。"""
        return await generate_questions_pydantic(
            knowledge_points=knowledge_points,
            difficulty=difficulty,
            quantity=str(quantity),
        )

    return agent


# ── SSE 事件适配层 ──

def _tool_category(name: str) -> str:
    return name.split("_")[0] if "_" in name else name


class _SSEAdapter:
    """状态机：跟踪当前阶段，将 AgentStreamEvent 映射为 SSE JSON 字符串列表"""

    def __init__(self):
        self._phase = "thinking"        # thinking | executing | reply
        self._tool_name = None
        self._pending_tool_id = None

    def feed(self, event) -> list[str]:
        """处理一个事件，返回 SSE JSON 字符串列表（可能 0/1/2 个）"""
        from pydantic_ai.messages import (
            PartStartEvent, PartDeltaEvent, PartEndEvent,
            TextPartDelta,
            FunctionToolCallEvent, FunctionToolResultEvent,
            FinalResultEvent,
        )

        # --- PartStartEvent ---
        if isinstance(event, PartStartEvent):
            return []

        # --- PartDeltaEvent ---
        if isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                results = []
                if self._phase != "reply":
                    self._phase = "reply"
                    results.append(json.dumps(
                        {"type": "phase", "phase": "reply"}, ensure_ascii=False
                    ))
                results.append(json.dumps(
                    {"type": "text", "content": event.delta.content_delta},
                    ensure_ascii=False,
                ))
                return results
            return []

        # --- PartEndEvent ---
        if isinstance(event, PartEndEvent):
            return []

        # --- FunctionToolCallEvent ---
        if isinstance(event, FunctionToolCallEvent):
            self._tool_name = event.part.tool_name
            self._pending_tool_id = event.part.tool_call_id
            return [json.dumps(
                {
                    "type": "tool_call",
                    "name": event.part.tool_name,
                    "tool": _tool_category(event.part.tool_name),
                    "args": event.part.args,
                },
                ensure_ascii=False,
            )]

        # --- FunctionToolResultEvent ---
        if isinstance(event, FunctionToolResultEvent):
            success = True
            # event.result is a ToolReturnPart — extract .content for the actual string
            raw = event.result
            if hasattr(raw, 'content'):
                result_str = str(raw.content)
            else:
                result_str = str(raw)
            try:
                data = json.loads(result_str)
                if isinstance(data, dict) and "error" in data:
                    success = False
            except (json.JSONDecodeError, TypeError):
                pass
            tool_name = self._tool_name or "unknown"
            return [json.dumps(
                {
                    "type": "tool_result",
                    "name": tool_name,
                    "tool": _tool_category(tool_name),
                    "success": success,
                    "result": result_str[:8000],
                },
                ensure_ascii=False,
            )]

        # --- FinalResultEvent (ignore — internal signal, not end-of-stream) ---
        if isinstance(event, FinalResultEvent):
            return []

        return []


async def stream_to_sse(user_message: str, history: list[dict] = None, use_chem_agent: bool = False) -> AsyncIterator[str]:
    """流式对话，输出 SSE 格式事件（pydantic-ai 1.107.0 run_stream_events）

    Args:
        user_message: 用户消息
        history: 对话历史（Phase 0 暂未使用，Phase 3 接入）
        use_chem_agent: True 使用双 tool agent（search + generate），False 只用 search
    """
    agent = create_chem_agent() if use_chem_agent else create_search_agent()
    adapter = _SSEAdapter()

    # Phase: thinking
    yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

    async with agent.run_stream_events(user_message) as stream:
        async for event in stream:
            for result in adapter.feed(event):
                yield f"data: {result}\n\n"

    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
