# -*- coding: utf-8 -*-
"""Phase 0.3: DeepSeek + ChatOpenAI bind_tools + ReAct loop 验证"""
import os, json, asyncio, sys
from dotenv import load_dotenv
load_dotenv()

DS_KEY = os.getenv("DEEPSEEK_API_KEY", "")
if not DS_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set")
    sys.exit(1)

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# ── 模拟 ChemAI tools ──

@tool
async def search_exam_bank(keyword: str, limit: int = 5) -> str:
    """搜索历年高考化学真题。按知识点关键词筛选。"""
    return json.dumps({
        "total": 3,
        "questions": [
            {"content": f"{keyword}相关真题1 - 2024全国卷", "answer": "C", "difficulty": "medium"},
            {"content": f"{keyword}相关真题2 - 2023北京卷", "answer": "A", "difficulty": "hard"},
            {"content": f"{keyword}相关真题3 - 2022全国卷", "answer": "B", "difficulty": "easy"},
        ]
    }, ensure_ascii=False)

@tool
async def generate_questions(knowledge_points: str, quantity: int = 5, difficulty: str = "medium") -> str:
    """根据知识点生成高中化学选择题。返回题目列表。"""
    # Simulated — in real code this calls DeepSeekProvider
    return json.dumps({
        "total": quantity,
        "questions": [
            {"content": f"关于{knowledge_points}的选择题{i+1}", "answer": chr(65+i%4), "difficulty": difficulty}
            for i in range(quantity)
        ],
        "_route": {"navigate": True, "page": "exam-v2", "actions": [{"action": "openTab", "payload": "generate"}]}
    }, ensure_ascii=False)

@tool
async def request_approval(message: str, context: str = "") -> str:
    """向老师请求确认。生成内容后需要老师审核时调用。只在真正需要人为判断时用。"""
    from langgraph.types import interrupt
    interrupt({"type": "approval", "message": message, "context": context})
    return json.dumps({"status": "approved", "note": "老师已确认"})

@tool
async def save_to_bank(questions_json: str, folder: str = "默认文件夹") -> str:
    """将题目保存到题库。"""
    data = json.loads(questions_json) if isinstance(questions_json, str) else questions_json
    count = data.get("total", len(data.get("questions", [])))
    return json.dumps({"saved": count, "folder": folder}, ensure_ascii=False)


async def main():
    TOOLS = [search_exam_bank, generate_questions, request_approval, save_to_bank]

    model = ChatOpenAI(
        model="deepseek-chat",
        api_key=DS_KEY,
        base_url="https://api.deepseek.com/v1",
        temperature=0.3,
        max_tokens=4096,
    )

    system_prompt = """你是高中化学教研助手。你可以使用工具来完成教师的需求。

核心规则:
1. 教师提到出题/考试相关需求时，先确认必要信息（知识点、数量、难度、给哪个班）
2. 出完题后，调用 request_approval 请老师预览
3. 老师确认后，调用 save_to_bank 保存到题库
4. 闲聊或纯知识问答直接回复，不调工具
5. 不确定参数时先反问，不要猜测"""

    agent = create_react_agent(
        model=model,
        tools=TOOLS,
        prompt=system_prompt,
    )

    # ── Test 1: Chat (no tools expected) ──
    print("=" * 60)
    print("Test 1: 闲聊 — 不应调 tool")
    print("=" * 60)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "你好"}]},
        {"configurable": {"thread_id": "test-1"}},
    )
    msgs = result.get("messages", [])
    tool_calls = [m for m in msgs if hasattr(m, "tool_calls") and m.tool_calls]
    if tool_calls:
        print(f"  WARN: LLM 调了 tool (不期望): {[tc['name'] for m in tool_calls for tc in m.tool_calls]}")
    else:
        print("  PASS: 闲聊不调 tool")
    last = msgs[-1]
    print(f"  回复: {last.content[:100]}..." if hasattr(last, "content") and last.content else "  回复: (空)")
    print()

    # ── Test 2: Simple tool call ──
    print("=" * 60)
    print("Test 2: 单 tool 调用 — 搜索真题")
    print("=" * 60)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "搜索3条盐类水解的高考真题"}]},
        {"configurable": {"thread_id": "test-2"}},
    )
    msgs = result.get("messages", [])
    tool_calls = [m for m in msgs if hasattr(m, "tool_calls") and m.tool_calls]
    executed = [m for m in msgs if hasattr(m, "type") and m.type == "tool"]
    print(f"  Tool calls (LLM 请求): {len(tool_calls)}")
    print(f"  Tools executed: {len(executed)}")
    if executed:
        print(f"  Tool names: {[m.name for m in executed]}")
    print(f"  最终回复: {msgs[-1].content[:200] if hasattr(msgs[-1], 'content') and msgs[-1].content else '(空)'}"[:200])

    # ── Test 3: Multi-step with tool chain ──
    print()
    print("=" * 60)
    print("Test 3: 多步流程 — 出题→确认→入库")
    print("=" * 60)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "帮我出3道关于氧化还原反应的选择题，中等难度，出完请我确认"}]},
        {"configurable": {"thread_id": "test-3"}},
    )
    msgs = result.get("messages", [])
    executed = [m for m in msgs if hasattr(m, "type") and m.type == "tool"]
    tool_names = [m.name for m in executed]
    print(f"  工具执行序列: {tool_names}")
    # Check: should generate, then request_approval, then (maybe) save
    has_generate = "generate_questions" in tool_names
    has_approval = "request_approval" in tool_names
    has_save = "save_to_bank" in tool_names
    print(f"  生成题目: {'PASS' if has_generate else 'WARN'}  |  确认步骤: {'PASS' if has_approval else 'WARN'}  |  保存: {'PASS' if has_save else 'SKIP (approval not resumed)'}")
    print()

    # ── Test 4: Agent asks clarifying questions ──
    print("=" * 60)
    print("Test 4: Agent 反问 — 信息不足时应该先问")
    print("=" * 60)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "帮我准备一份期中考试"}]},
        {"configurable": {"thread_id": "test-4"}},
    )
    msgs = result.get("messages", [])
    last = msgs[-1]
    content = last.content if hasattr(last, "content") and last.content else ""
    executed = [m for m in msgs if hasattr(m, "type") and m.type == "tool"]
    tool_names = [m.name for m in executed]
    print(f"  工具序列: {tool_names}")
    # Agent should ask questions, not blindly generate
    if "generate_questions" in tool_names and len(content) < 50:
        print("  WARN: Agent 直接出题了，没有先确认参数（可能 prompt 不够强）")
    elif "generate_questions" not in tool_names:
        print("  PASS: Agent 没有盲目出题，先反问教师")
    else:
        print("  OK: Agent 出了题但最终也有文本回复")
    print(f"  最终回复（前 300 字符）: {content[:300]}")

    print()
    print("=" * 60)
    print("  Phase 0.3 complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
