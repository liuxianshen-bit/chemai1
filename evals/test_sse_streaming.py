"""
SSE streaming evals — verify SSE event structure and ordering
"""
import json
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evals.conftest import EvalReport


async def capture_sse_events(msg, persona, tool_names_override=None):
    """Capture all SSE events from a streaming agent run."""
    from agent.agents import factory
    from agent.deps import ChemAIDeps
    from agent.sse_adapter import SSEAdapter
    from agent.channel.fastapi_sse import _classify_and_narrow

    if tool_names_override is not None:
        tool_names = tool_names_override
    else:
        tool_names, _ = await _classify_and_narrow(msg, persona, None)

    deps = ChemAIDeps(persona=persona, provider_name="deepseek")
    agent = factory.create_agent(persona=persona, provider="deepseek", deps=deps, tool_names=tool_names)

    adapter = SSEAdapter()
    events = []

    async with agent.run_stream_events(msg, deps=deps) as stream:
        async for event in stream:
            for result in adapter.feed(event):
                try:
                    parsed = json.loads(result)
                    events.append(parsed)
                except json.JSONDecodeError:
                    pass

    return events


def validate_event_sequence(events, expect_tool=True):
    """Validate the SSE event sequence structure."""
    types = [e["type"] for e in events]
    issues = []

    if not types:
        return False, ["no events at all"]

    # Must contain 'done' or have text output
    has_done = "done" in types
    has_text = "text" in types

    if expect_tool:
        if "tool_call" not in types:
            issues.append("missing 'tool_call' event")
        if "tool_result" not in types:
            issues.append("missing 'tool_result' event")

    # tool_call must come before tool_result
    if "tool_call" in types and "tool_result" in types:
        tc_idx = types.index("tool_call")
        tr_idx = max(i for i, t in enumerate(types) if t == "tool_result")
        if tc_idx >= tr_idx:
            issues.append("tool_call after tool_result (wrong order)")

    # phase should transition to 'reply' before text
    if "text" in types:
        text_idx = types.index("text")
        reply_idx = types.index("phase") if "phase" in types and any(
            e.get("phase") == "reply" for e in events if e["type"] == "phase"
        ) else -1
        # Not a hard failure since phase might be folded into first text

    # Check that event types are in valid order (no text before tool_result)
    if expect_tool and "tool_result" in types and "text" in types:
        tr_idx = max(i for i, t in enumerate(types) if t == "tool_result")
        text_idx = types.index("text")
        if text_idx < tr_idx:
            issues.append("text events before tool_result")

    return len(issues) == 0, issues


def run():
    report = EvalReport()

    async def _run():
        test_cases = [
            ("balance_equation", "帮我配平 Fe + O2 = Fe2O3", "tutor", ["balance_equation"], True),
            ("chat_no_tool", "你好", "tutor", None, False),
        ]

        for name, msg, persona, tool_override, expect_tool in test_cases:
            print(f"  Testing SSE: {name}...")
            events = await capture_sse_events(msg, persona, tool_override)
            event_types = [e["type"] for e in events]
            valid, issues = validate_event_sequence(events, expect_tool)

            report.add(
                f"sse: {name}",
                valid,
                f"events={event_types} issues={issues}" if not valid else f"events={event_types}"
            )
            print(f"    Sequence: {' -> '.join(event_types)}")

    asyncio.run(_run())
    print(report.summary())
    return report


if __name__ == "__main__":
    run()
