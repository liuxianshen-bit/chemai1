"""LangGraph SSE Adapter v2 — astream_events → ChemAI SSE 事件格式.

Single-path adapter for single-agent mode. No sub_agent_depth tracking,
no route cards, no sub-agent panels. Tools and text flow directly.
"""

import json
import time


def _tool_category(name: str) -> str:
    return name.split("_")[0] if "_" in name else name


def _serialize_args(tool_input: dict) -> dict:
    return tool_input


class LangGraphSSEAdapterV2:
    """Simplified SSE adapter for single ReAct agent.

    Emits: tool_call, tool_result, phase, text, component, navigate, done.
    No sub_agent_start / sub_agent_end / subagent_text / route events.
    """

    def __init__(self):
        self._phase = "thinking"
        self._tool_results = []
        self._did_stream_text = False
        self._last_tool_text = ""       # last tool's text output (for dedup)
        self._reply_prefix = ""         # accumulate first chars of new reply
        self._skip_dedup = False        # dedup already decided for this reply
        self._tool_complete = False     # tool already gave a complete answer — skip LLM text

    def feed(self, event: dict) -> list[str]:
        event_type = event.get("event", "")
        name = event.get("name", "")
        data = event.get("data", {})

        # ── Tool start ──
        if event_type == "on_tool_start":
            if name == "request_approval":
                return [json.dumps({
                    "type": "phase", "phase": "awaiting_approval",
                    "message": data.get("input", {}).get("message", "请确认"),
                }, ensure_ascii=False)]
            return [json.dumps({
                "type": "tool_call", "name": name,
                "tool": _tool_category(name),
                "args": _serialize_args(data.get("input", {})),
            }, ensure_ascii=False)]

        # ── Tool end ──
        if event_type == "on_tool_end":
            if name == "request_approval":
                return []
            output = data.get("output", "")
            result_str = str(output) if not isinstance(output, str) else output
            success = True

            # Unwrap LangGraph ToolMessage repr: "content='...JSON...' additional_kwargs={...}"
            if result_str.startswith("content='") or result_str.startswith('content="'):
                quote_char = result_str[8]
                inner = result_str[9:]
                if inner.endswith(quote_char):
                    inner = inner[:-1]
                inner = inner.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
                result_str = inner

            # Extract structured images (raw_decode handles trailing content)
            image_events = []
            try:
                decoder = json.JSONDecoder()
                parsed, _ = decoder.raw_decode(result_str) if isinstance(result_str, str) else (result_str, 0)
                if isinstance(parsed, dict) and "images" in parsed:
                    # Replace result_str with just the text (LLM sees clean text)
                    result_str = parsed.get("text", result_str)
                    for img_entry in parsed.get("images", []):
                        if img_entry.get("urls"):
                            image_events.append(json.dumps({
                                "type": "exam_images",
                                "q_index": img_entry.get("q_index", 0),
                                "title": img_entry.get("title", ""),
                                "urls": img_entry.get("urls", []),
                            }, ensure_ascii=False))
                    # Store only text in _tool_results
                    self._tool_results.append({"tool_name": name, "result": {"text": result_str}})
                    # Store for text dedup (LLM should not echo tool guidance verbatim)
                    self._last_tool_text = result_str
                    # If tool returned structured tutoring response, skip LLM text after it
                    if "guidance" in parsed or "step" in parsed:
                        self._tool_complete = True
                elif isinstance(parsed, dict) and "error" in parsed:
                    success = False
                    self._tool_results.append({"tool_name": name, "result": parsed})
                else:
                    self._tool_results.append({"tool_name": name, "result": parsed})
            except Exception as exc:
                self._tool_results.append({
                    "tool_name": name,
                    "result": {"error": str(exc), "raw": str(result_str)[:500]},
                })
                success = False

            events = [json.dumps({
                "type": "tool_result", "name": name,
                "tool": _tool_category(name), "success": success,
                "result": result_str[:8000] if isinstance(result_str, str) else str(result_str)[:8000],
            }, ensure_ascii=False)]
            events.extend(image_events)
            return events

        # ── Text streaming ──
        if event_type == "on_chat_model_stream":
            # If tool already gave a complete answer, skip all LLM text
            if self._tool_complete:
                return []
            chunk = data.get("chunk", None)
            if chunk is None:
                return []
            content = getattr(chunk, "content", None)
            if not content:
                return []
            results = []
            if self._phase != "reply":
                self._phase = "reply"
                self._did_stream_text = False
                self._reply_prefix = ""
                self._skip_dedup = False
                results.append(json.dumps(
                    {"type": "phase", "phase": "reply"}, ensure_ascii=False
                ))
            # Dedup: check if new reply is just echoing the last tool output
            if not self._skip_dedup and self._last_tool_text:
                self._reply_prefix += content
                if len(self._reply_prefix) >= 50 or (not content.strip()):
                    self._skip_dedup = True  # decide once
                    prefix = self._reply_prefix.strip()
                    tool_prefix = self._last_tool_text.strip()[:len(prefix)]
                    # Heuristic: if first 50 chars overlap >70%, skip entire reply
                    if prefix and tool_prefix and self._text_similarity(prefix, tool_prefix) > 0.7:
                        return []  # skip — LLM echoing tool guidance
            self._did_stream_text = True
            results.append(json.dumps(
                {"type": "text", "content": content}, ensure_ascii=False
            ))
            return results

        return []

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Simple character-level similarity (Jaccard-like on char sets)."""
        if not a or not b:
            return 0.0
        set_a, set_b = set(a), set(b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def finalize(self, route: dict = None, component: dict = None,
                 result_text: str = None) -> list[str]:
        events = []

        # ── Component (inline panel) ──
        if component and component.get("component"):
            events.append(json.dumps({
                "type": "component",
                "component": component["component"],
                "params": component.get("params", {}),
            }, ensure_ascii=False))
        # ── Text result: only emit if NOT already streamed chunk-by-chunk ──
        elif result_text and not self._did_stream_text:
            events.append(json.dumps({
                "type": "text", "content": result_text,
            }, ensure_ascii=False))

        # ── Route ──
        if route and route.get("navigate"):
            events.append(json.dumps({
                "type": "navigate", "page": route.get("page"),
                "params": route.get("params", {}),
            }, ensure_ascii=False))
            pop = route.get("populate")
            if pop:
                events.append(json.dumps({
                    "type": "populate", "target": pop.get("target", ""),
                    "data": pop.get("data", {}),
                }, ensure_ascii=False))
            for act in route.get("actions", []):
                events.append(json.dumps({
                    "type": "action", "action": act.get("action", ""),
                    "payload": act.get("payload", ""),
                }, ensure_ascii=False))
        elif not route:
            # Fallback: check tool results for _route signals
            for tr in self._tool_results:
                r = tr.get("result", {}).get("_route")
                if r and r.get("navigate"):
                    events.append(json.dumps({
                        "type": "navigate", "page": r.get("page"),
                        "params": r.get("params", {}),
                    }, ensure_ascii=False))
                    pop = r.get("populate")
                    if pop:
                        events.append(json.dumps({
                            "type": "populate", "target": pop.get("target", ""),
                            "data": pop.get("data", {}),
                        }, ensure_ascii=False))
                    for act in r.get("actions", []):
                        events.append(json.dumps({
                            "type": "action", "action": act.get("action", ""),
                            "payload": act.get("payload", ""),
                        }, ensure_ascii=False))
                    break

        events.append(json.dumps({"type": "done"}, ensure_ascii=False))
        events.append("[DONE]")
        return events
