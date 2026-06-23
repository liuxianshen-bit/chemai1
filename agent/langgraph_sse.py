"""LangGraph SSE Adapter — astream_events → ChemAI SSE 事件格式.

与现有 SSEAdapter 输出 100% 兼容。
"""
import json


def _tool_category(name: str) -> str:
    """Extract tool category prefix from tool name."""
    return name.split("_")[0] if "_" in name else name


def _serialize_args(tool_input: dict) -> dict:
    """Pass through raw tool call args dict (matching pydantic-ai behavior)."""
    return tool_input


class LangGraphSSEAdapter:
    """State machine: maps astream_events() output to ChemAI SSE JSON strings.

    Key design:
    - feed() handles streaming events (text, tool_call, tool_result)
    - finalize() handles post-stream events (navigate, populate, action, done)
    - _phase tracks thinking→reply transition
    - _tool_results collects all tool results for _route extraction
    """

    def __init__(self):
        self._phase = "thinking"
        self._tool_results = []

    def feed(self, event: dict) -> list[str]:
        """Process one astream event, return SSE JSON string list."""
        event_type = event.get("event", "")
        name = event.get("name", "")
        data = event.get("data", {})

        # ── LLM token streaming → text ──
        if event_type == "on_chat_model_stream":
            chunk = data.get("chunk", None)
            if chunk is None:
                return []
            content = getattr(chunk, "content", None)
            if not content:
                return []
            results = []
            if self._phase != "reply":
                self._phase = "reply"
                results.append(json.dumps(
                    {"type": "phase", "phase": "reply"}, ensure_ascii=False
                ))
            results.append(json.dumps(
                {"type": "text", "content": content}, ensure_ascii=False
            ))
            return results

        # ── Tool start ──
        if event_type == "on_tool_start":
            # request_approval special handling
            if name == "request_approval":
                tool_input = data.get("input", {})
                msg = tool_input.get("message", "请确认")
                return [json.dumps({
                    "type": "phase",
                    "phase": "awaiting_approval",
                    "message": msg,
                }, ensure_ascii=False)]

            return [json.dumps({
                "type": "tool_call",
                "name": name,
                "tool": _tool_category(name),
                "args": _serialize_args(data.get("input", {})),
            }, ensure_ascii=False)]

        # ── Tool end ──
        if event_type == "on_tool_end":
            # request_approval: suppress tool_result SSE
            if name == "request_approval":
                return []

            output = data.get("output", "")
            result_str = str(output) if not isinstance(output, str) else output

            # Parse for success check and _route collection
            success = True
            try:
                parsed = json.loads(result_str) if isinstance(result_str, str) else result_str
                if isinstance(parsed, dict) and "error" in parsed:
                    success = False
                # Collect _route for finalize()
                self._tool_results.append({
                    "tool_name": name,
                    "result": parsed,
                })
            except (json.JSONDecodeError, TypeError):
                self._tool_results.append({
                    "tool_name": name,
                    "result": {"raw": str(result_str)[:500]},
                })

            return [json.dumps({
                "type": "tool_result",
                "name": name,
                "tool": _tool_category(name),
                "success": success,
                "result": result_str[:8000] if isinstance(result_str, str) else str(result_str)[:8000],
            }, ensure_ascii=False)]

        return []

    def finalize(self, route: dict = None, component: dict = None) -> list[str]:
        """Called after astream_events() completes.
        Emits component/navigate/populate/action events, then done + [DONE] sentinel.

        Args:
            route: Optional route dict from GuardState.last_route.
            component: Optional component dict from GuardState.last_component.
        """
        events = []

        # ── Component: inline UI in chat ──
        if component and component.get("component"):
            events.append(json.dumps({
                "type": "component",
                "component": component["component"],
                "params": component.get("params", {}),
            }, ensure_ascii=False))

        # Use explicit route if provided (from guard_state), fall back to _tool_results
        if route and route.get("navigate"):
            events.append(json.dumps({
                "type": "navigate",
                "page": route.get("page"),
                "params": route.get("params", {}),
            }, ensure_ascii=False))

            pop = route.get("populate")
            if pop:
                events.append(json.dumps({
                    "type": "populate",
                    "target": pop.get("target", ""),
                    "data": pop.get("data", {}),
                }, ensure_ascii=False))

            for act in route.get("actions", []):
                events.append(json.dumps({
                    "type": "action",
                    "action": act.get("action", ""),
                    "payload": act.get("payload", ""),
                }, ensure_ascii=False))

        elif not route:
            # Fallback: extract _route from collected tool results (legacy path)
            for tr in self._tool_results:
                r = tr.get("result", {}).get("_route")
                if r and r.get("navigate"):
                    events.append(json.dumps({
                        "type": "navigate",
                        "page": r.get("page"),
                        "params": r.get("params", {}),
                    }, ensure_ascii=False))

                    pop = r.get("populate")
                    if pop:
                        events.append(json.dumps({
                            "type": "populate",
                            "target": pop.get("target", ""),
                            "data": pop.get("data", {}),
                        }, ensure_ascii=False))

                    for act in r.get("actions", []):
                        events.append(json.dumps({
                            "type": "action",
                            "action": act.get("action", ""),
                            "payload": act.get("payload", ""),
                        }, ensure_ascii=False))

                    break  # Only first navigation trigger

        events.append(json.dumps({"type": "done"}, ensure_ascii=False))
        events.append("[DONE]")
        return events
