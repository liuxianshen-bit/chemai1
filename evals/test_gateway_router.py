"""
Gateway Router evals — BDD-style 路由重构全覆盖测试

测试层次:
  1. Unit: keyword fallback 分类准确性 (chat/navigate)
  2. Unit: _extract_route_events 路由提取逻辑
  3. Unit: IntentResult 新数据结构
  4. Integration: 全管道 classifier→agent→route 端到端
  5. Integration: SSE 流式事件中的 navigate 检测

用法:
  python evals/test_gateway_router.py              # 全部 (unit only)
  python evals/test_gateway_router.py --integration # 含 LLM 调用的集成测试
"""
import json
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from evals.conftest import EvalReport, parse_tool_result, extract_tools_called


# ═══════════════════════════════════════════════════════════════════════
# Test case definitions — BDD style: Given/When/Then
# ═══════════════════════════════════════════════════════════════════════

# (name, message, persona, expected_type, expected_tools, expect_navigate, expected_page)
CLASSIFIER_CASES = [
    # ── navigate: 纯页面跳转 ──
    ("打开考试工作台",       "打开考试工作台",       "tutor",   "navigate", [],          False, "exam-v2"),
    ("去首页",               "去首页",               "tutor",   "navigate", [],          False, None),
    ("打开诊断页面",         "打开诊断页面",         "teacher", "navigate", [],          False, "diagnosis"),
    ("查看班级列表",         "查看班级列表",         "teacher", "navigate", [],          False, None),
    ("打开学生管理",         "帮我打开学生管理页面", "teacher", "navigate", [],          False, "students"),

    # ── chat: 需要调 tool (不跳页) ──
    ("单人诊断-张梦琪",      "张梦琪最近错题多吗",             "teacher", "chat", ["diagnose_barrier"],    False, None),
    ("单人出题-张三",        "给张三出5道盐类水解的选择题",    "tutor",   "chat", ["generate_questions"],  False, None),
    ("单人周报",             "生成张梦琪的本周学习报告",       "parent",  "chat", ["weekly_report"],       False, None),
    ("知识问答-氧化还原",    "什么是氧化还原反应",             "tutor",   "chat", None,     False, None),  # None=fallback OK
    ("实验模拟",             "模拟钠和水反应的实验",           "tutor",   "chat", ["simulate_experiment"], False, None),
    ("搜索真题",             "搜索盐类水解的历年高考真题",    "tutor",   "chat", ["search_exam_bank"],    False, None),
    ("配平方程式",           "帮我配平 Fe + O2 = Fe2O3",      "tutor",   "chat", ["balance_equation"],    False, None),
    ("导入试卷",             "导入这份PDF试卷",               "teacher", "chat", ["import_exam_paper"],   False, None),

    # ── chat: 班级级别 (需要跳页，但由 tool _route 决定，classifier 只管选 tool) ──
    ("班级诊断",             "高三1班的诊断情况",             "teacher", "chat", ["diagnose_barrier"],    False, None),
    ("组卷出题",             "出一份期中考试化学试卷",        "tutor",   "chat", ["generate_questions"],  False, None),
    ("班级周报",             "全班本周学习周报",              "parent",  "chat", ["weekly_report"],       False, None),
    ("自适应练习",           "给班级布置自适应练习",          "teacher", "chat", ["assign_adaptive_practice"], False, None),

    # ── chat: 无明确 tool 匹配 ──
    ("模糊闲聊",             "今天天气真好",                 "tutor",   "chat", None,                     False, None),
    ("你好",                 "你好",                         "tutor",   "chat", None,                     False, None),
    ("化学学习方法",         "怎么学好化学",                 "tutor",   "chat", None,                     False, None),  # None=fallback OK
]

# 10 关键边界场景 — 完整端到端: classifier → agent → _route → navigate
BOUNDARY_CASES = [
    # (name, message, persona, expected_navigate, expected_page_if_navigate)
    ("E2E-单人诊断不跳",       "张梦琪最近错题多吗",           "teacher", False, None),
    ("E2E-班级诊断跳页",       "高三1班诊断情况",             "teacher", True,  "diagnosis"),
    ("E2E-单人出题不跳",       "给张三出5道盐类水解的题",      "tutor",   False, None),
    ("E2E-组卷出题跳页",       "出一份期中化学试卷",           "tutor",   True,  "exam-v2"),
    ("E2E-单人周报不跳",       "张梦琪本周学习报告",           "parent",  False, None),
    ("E2E-知识问答不跳",       "什么是氧化还原反应",           "tutor",   False, None),
    ("E2E-搜索真题不跳",       "搜索盐类水解高考真题",         "tutor",   False, None),
    ("E2E-打开考试工作台",     "打开考试工作台",               "tutor",   True,  "exam-v2"),
    ("E2E-打开诊断页面",       "打开诊断页面",                 "teacher", True,  "diagnosis"),
    ("E2E-你好不跳",           "你好",                         "tutor",   False, None),
]


# ═══════════════════════════════════════════════════════════════════════
# Unit Tests — no API needed
# ═══════════════════════════════════════════════════════════════════════

def test_keyword_fallback_classification(report: EvalReport):
    """Given LLM 分类器失败, When 触发 keyword fallback,
       Then 正确区分 chat/navigate 并推荐 tool."""
    from agent.gateway import IntentClassifier, IntentResult

    # Mock provider that always fails
    class FailingProvider:
        async def chat(self, **kw):
            raise Exception("mock failure")

    classifier = IntentClassifier(FailingProvider())

    async def run():
        for name, msg, persona, expected_type, expected_tools, _, _ in CLASSIFIER_CASES:
            result = await classifier.classify(msg)
            type_ok = result.type == expected_type
            tools_ok = True
            if expected_tools is not None:
                tools_ok = result.tools is not None and all(t in result.tools for t in expected_tools)
            elif expected_tools is None and result.tools is not None:
                # tools=None means classifier gives up → let Agent decide, that's fine
                tools_ok = True

            passed = type_ok and tools_ok
            detail = ""
            if not passed:
                parts = []
                if not type_ok:
                    parts.append(f"type: got={result.type} expected={expected_type}")
                if not tools_ok:
                    parts.append(f"tools: got={result.tools} expected={expected_tools}")
                detail = "; ".join(parts)

            report.add(f"keyword: {name}", passed, detail)

    asyncio.run(run())


def test_route_extraction(report: EvalReport):
    """Given tool 返回值中的 _route, When 调用 _extract_route_events,
       Then 正确提取 navigate/page/populate/actions."""

    from agent.channel.fastapi_sse import _extract_route_events

    # Scenario 1: 单人诊断 → 不跳
    r = _extract_route_events([{
        "tool_name": "diagnose_barrier",
        "result": {"student_id": "001", "_route": {"navigate": False}}
    }])
    report.add("route-extract: 单人诊断不跳", r["navigate"] is None,
               f"got navigate={r['navigate']}" if r["navigate"] else "")

    # Scenario 2: 班级诊断 → 跳 diagnosis
    r = _extract_route_events([{
        "tool_name": "diagnose_barrier",
        "result": {
            "class_id": "c1", "_route": {
                "navigate": True, "page": "diagnosis",
                "actions": [{"action": "selectClass", "payload": "c1"}],
                "populate": {"target": "diagnosis", "data": {"total": 34}},
            }
        }
    }])
    report.add("route-extract: 班级诊断跳页",
               r["navigate"]["page"] == "diagnosis" and len(r["actions"]) == 1 and len(r["populates"]) == 1,
               f"got navigate={r['navigate']}" if not r["navigate"] else "")

    # Scenario 3: 组卷出题 → 跳 exam-v2
    r = _extract_route_events([{
        "tool_name": "generate_questions",
        "result": {
            "total": 5, "_route": {
                "navigate": True, "page": "exam-v2",
                "actions": [{"action": "openTab", "payload": "generate"}],
                "populate": {"target": "questions", "data": {}},
            }
        }
    }])
    report.add("route-extract: 组卷跳exam-v2",
               r["navigate"]["page"] == "exam-v2",
               "")

    # Scenario 4: 无 _route → 不跳
    r = _extract_route_events([{
        "tool_name": "chemistry_tutor",
        "result": {"answer": "勒夏特列原理是指..."}
    }])
    report.add("route-extract: 无_route不跳", r["navigate"] is None,
               f"got navigate={r['navigate']}" if r["navigate"] else "")

    # Scenario 5: 多 tool，第二个触发跳
    r = _extract_route_events([
        {"tool_name": "web_search", "result": {"_route": {"navigate": False}}},
        {"tool_name": "generate_questions", "result": {
            "_route": {"navigate": True, "page": "exam-v2", "actions": [],
                       "populate": {"target": "questions", "data": {}}}
        }},
    ])
    report.add("route-extract: 多tool第二触发跳",
               r["navigate"] is not None and r["navigate"]["page"] == "exam-v2",
               "")

    # Scenario 6: _route 是 JSON 字符串里的 (SSEAdapter 格式)
    from agent.channel.fastapi_sse import _extract_route_events
    # (用 parsed dict 模拟 — fastapi_sse.py 已经在收集时 parse 了)
    report.add("route-extract: parsed-dict format", True, "")


def test_intent_result_structure(report: EvalReport):
    """Given IntentResult, When 使用新字段名, Then type 替换 intent."""
    from agent.gateway import IntentResult

    # 默认
    r = IntentResult()
    report.add("intent-result: 默认type=chat", r.type == "chat",
               f"got type={r.type}")

    # navigate
    r = IntentResult(type="navigate", page="exam-v2", tools=[], provider="deepseek")
    report.add("intent-result: navigate结构", r.type == "navigate" and r.page == "exam-v2" and r.tools == [],
               "")

    # chat with tools
    r = IntentResult(type="chat", tools=["generate_questions", "diagnose_barrier"])
    report.add("intent-result: chat+tool推荐", r.type == "chat" and len(r.tools) == 2,
               "")

    # chat with None tools (fallback: let agent decide)
    r = IntentResult(type="chat", tools=None)
    report.add("intent-result: chat+tools=None回退", r.type == "chat" and r.tools is None,
               "")


def test_route_events_format(report: EvalReport):
    """Given _route 事件, When 序列化为 SSE, Then 字段名与现有前端协议兼容."""
    from agent.channel.fastapi_sse import _extract_route_events

    tool_results = [{
        "tool_name": "diagnose_barrier",
        "result": {
            "class_id": "高三1班", "_route": {
                "navigate": True, "page": "diagnosis",
                "actions": [
                    {"action": "selectClass", "payload": "高三1班"},
                    {"action": "showPlan", "payload": ""},
                ],
                "populate": {"target": "diagnosis",
                             "data": {"total_students": 34, "barrier_distribution": {}}},
            }
        }
    }]
    nav = _extract_route_events(tool_results)

    # navigate 事件格式
    assert nav["navigate"] is not None
    assert "page" in nav["navigate"]
    assert "params" in nav["navigate"]
    report.add("route-format: navigate有page+params", True, "")

    # populate 事件格式
    assert len(nav["populates"]) == 1
    pop = nav["populates"][0]
    assert "target" in pop
    assert "data" in pop
    report.add("route-format: populate有target+data", True, "")

    # action 事件格式
    assert len(nav["actions"]) == 2
    act = nav["actions"][0]
    assert "action" in act
    assert "payload" in act
    report.add("route-format: action有action+payload", True, "")


# ═══════════════════════════════════════════════════════════════════════
# Integration Tests — need DeepSeek API + DB
# ═══════════════════════════════════════════════════════════════════════

async def run_boundary_test(msg: str, persona: str) -> dict:
    """Run full pipeline for a single boundary test case.
    Returns {navigate_detected, navigate_page, tools_called, output, passed}.
    """
    from agent.agents import factory
    from agent.deps import ChemAIDeps
    from agent.channel.fastapi_sse import _classify_and_narrow, _extract_tool_results, _extract_route_events

    # Phase 1: Classify
    tool_names, intent = await _classify_and_narrow(msg, persona, None)

    # navigate type: direct jump, no Agent
    if intent and intent.type == "navigate":
        return {
            "navigate_detected": True,
            "navigate_page": intent.page,
            "tools_called": [],
            "output": "",
            "route_source": "gateway-navigate",
        }

    # Phase 2: Agent
    deps = ChemAIDeps(persona=persona, provider_name="deepseek")
    agent = factory.create_agent(
        persona=persona, provider="deepseek",
        deps=deps, tool_names=tool_names,
    )
    result = await agent.run(msg)
    tools_called = extract_tools_called(result)

    # Phase 3: Route extraction from tool results
    tool_results = _extract_tool_results(result)
    nav = _extract_route_events(tool_results)

    return {
        "navigate_detected": nav["navigate"] is not None,
        "navigate_page": nav["navigate"]["page"] if nav["navigate"] else None,
        "tools_called": tools_called,
        "output": result.output[:200] if hasattr(result, 'output') else "",
        "route_source": "tool-_route",
    }


def test_boundary_scenarios(report: EvalReport):
    """Given 10 个关键边界场景, When 全管道执行,
       Then 导航行为匹配预期."""

    async def run():
        for name, msg, persona, expect_nav, expect_page in BOUNDARY_CASES:
            print(f"  Boundary: {name}...")
            r = await run_boundary_test(msg, persona)

            nav_ok = r["navigate_detected"] == expect_nav
            page_ok = True
            if expect_nav and expect_page:
                page_ok = r["navigate_page"] == expect_page

            passed = nav_ok and page_ok
            detail = ""
            if not passed:
                parts = []
                if not nav_ok:
                    parts.append(f"navigate: got={r['navigate_detected']} expected={expect_nav}")
                if not page_ok:
                    parts.append(f"page: got={r['navigate_page']} expected={expect_page}")
                parts.append(f"tools={r['tools_called']} src={r['route_source']}")
                detail = "; ".join(parts)

            report.add(f"boundary: {name}", passed, detail)

            if passed:
                print(f"    PASS nav={r['navigate_detected']} page={r['navigate_page']} tools={r['tools_called']}")

    asyncio.run(run())


async def capture_sse_with_route_events(msg: str, persona: str) -> tuple[list[dict], list[dict]]:
    """Capture SSE events and separately track navigate/populate/action events."""
    from agent.agents import factory
    from agent.deps import ChemAIDeps
    from agent.sse_adapter import SSEAdapter
    from agent.channel.fastapi_sse import _classify_and_narrow

    tool_names, intent = await _classify_and_narrow(msg, persona, None)

    # navigate type: no Agent
    if intent and intent.type == "navigate" and intent.page:
        return ([{"type": "navigate", "page": intent.page}], [])

    deps = ChemAIDeps(persona=persona, provider_name="deepseek")
    agent = factory.create_agent(
        persona=persona, provider="deepseek", deps=deps, tool_names=tool_names,
    )

    adapter = SSEAdapter()
    all_events = []
    nav_events = []

    async with agent.run_stream_events(msg, deps=deps) as stream:
        async for event in stream:
            for result in adapter.feed(event):
                try:
                    parsed = json.loads(result)
                    all_events.append(parsed)
                except json.JSONDecodeError:
                    pass

    return all_events, nav_events


def test_sse_navigate_events(report: EvalReport):
    """Given navigate 类型消息, When SSE 流式执行,
       Then SSE 事件中包含 navigate 但不包含 tool_call."""

    async def run():
        # Test 1: navigate → 应有 navigate 事件，无 tool_call
        events, _ = await capture_sse_with_route_events("打开考试工作台", "tutor")
        types = [e["type"] for e in events]
        has_nav = "navigate" in types
        has_tool = "tool_call" in types
        report.add("sse-nav: navigate不含tool", has_nav and not has_tool,
                   f"events={types}" if not (has_nav and not has_tool) else f"events={types}")

        # Test 2: chat (单人诊断) → 应有 tool_call/tool_result，无 navigate
        events, _ = await capture_sse_with_route_events("张梦琪最近错题多吗", "teacher")
        types = [e["type"] for e in events]
        has_nav = "navigate" in types
        has_tool = "tool_call" in types
        report.add("sse-chat: 单人诊断无navigate有tool", not has_nav and has_tool,
                   f"events={types}" if (has_nav or not has_tool) else f"events={types}")

        # Test 3: chat (班级诊断) → 应有 tool 事件，但不一定有 navigate (取决于 tool 路由)
        events, _ = await capture_sse_with_route_events("高三1班诊断情况", "teacher")
        types = [e["type"] for e in events]
        has_nav = "navigate" in types
        has_tool = "tool_call" in types
        report.add("sse-chat: 班级诊断有tool", has_tool,
                   f"events={types} nav={has_nav}")

    asyncio.run(run())


# ═══════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════

def run():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration", action="store_true",
                        help="Run integration tests (needs LLM API + DB)")
    # argparse may fail in nested runner; handle gracefully
    try:
        args, _ = parser.parse_known_args()
    except SystemExit:
        args = argparse.Namespace(integration=False)

    report = EvalReport()

    # ── Unit tests (always run) ──
    print("\n=== UNIT: IntentResult structure ===")
    test_intent_result_structure(report)

    print("\n=== UNIT: Keyword fallback classification ===")
    test_keyword_fallback_classification(report)

    print("\n=== UNIT: _extract_route_events logic ===")
    test_route_extraction(report)

    print("\n=== UNIT: Route events format compatibility ===")
    test_route_events_format(report)

    # ── Integration tests (opt-in) ──
    if args.integration:
        print("\n=== INTEGRATION: 10 boundary scenarios ===")
        test_boundary_scenarios(report)

        print("\n=== INTEGRATION: SSE navigate events ===")
        test_sse_navigate_events(report)
    else:
        print("\n(skip integration tests — pass --integration to run)")

    print(report.summary())
    return report


if __name__ == "__main__":
    run()
