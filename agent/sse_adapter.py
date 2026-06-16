"""SSE 事件适配器 — pydantic-ai AgentStreamEvent → ChemAI SSE 格式"""
import json
from typing import AsyncIterator


def _tool_category(name: str) -> str:
    return name.split("_")[0] if "_" in name else name


class SSEAdapter:
    """状态机：跟踪当前阶段，将 AgentStreamEvent 映射为 SSE JSON 字符串列表"""

    def __init__(self):
        self._phase = "thinking"
        self._tool_name = None

    def feed(self, event) -> list[str]:
        """处理一个事件，返回 SSE JSON 字符串列表（0/1/2 个）"""
        from pydantic_ai.messages import (
            PartStartEvent, PartDeltaEvent, PartEndEvent,
            TextPartDelta,
            FunctionToolCallEvent, FunctionToolResultEvent,
            FinalResultEvent,
        )

        if isinstance(event, PartStartEvent):
            return []

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

        if isinstance(event, PartEndEvent):
            return []

        if isinstance(event, FunctionToolCallEvent):
            self._tool_name = event.part.tool_name
            return [json.dumps({
                "type": "tool_call",
                "name": event.part.tool_name,
                "tool": _tool_category(event.part.tool_name),
                "args": event.part.args,
            }, ensure_ascii=False)]

        if isinstance(event, FunctionToolResultEvent):
            success = True
            raw = event.result
            result_str = str(raw.content) if hasattr(raw, 'content') else str(raw)
            try:
                data = json.loads(result_str)
                if isinstance(data, dict) and "error" in data:
                    success = False
            except (json.JSONDecodeError, TypeError):
                pass
            tool_name = getattr(raw, 'tool_name', None) or self._tool_name or 'unknown'
            return [json.dumps({
                "type": "tool_result",
                "name": tool_name,
                "tool": _tool_category(tool_name),
                "success": success,
                "result": result_str[:8000],
            }, ensure_ascii=False)]

        if isinstance(event, FinalResultEvent):
            return []

        return []


async def pydantic_stream_to_sse(
    agent,
    user_message: str,
    deps=None,
    message_history=None,
) -> AsyncIterator[str]:
    """流式对话，输出 SSE 格式事件。

    Args:
        agent: pydantic-ai Agent 实例
        user_message: 用户消息
        deps: ChemAIDeps 或 None
        message_history: pydantic-ai message_history 或 None
    """
    adapter = SSEAdapter()

    # Phase: thinking
    yield f"data: {json.dumps({'type': 'phase', 'phase': 'thinking'}, ensure_ascii=False)}\n\n"

    async with agent.run_stream_events(
        user_message,
        deps=deps,
        message_history=message_history,
    ) as stream:
        async for event in stream:
            for result in adapter.feed(event):
                yield f"data: {result}\n\n"

    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"
