# LangGraph Agent 迁移 — 架构设计

## Context

pydantic-ai 的 Agent 类做的事：LLM 接收 user_message + tools → 决定调不调 tool → 调了就等结果 → 写回复。一次交互，一个 tool，一个回复。

真实教学场景不是这样。老师说"帮我准备期中考试"——agent 需要自己拆解：问范围、问班级、搜真题、出题、配平检查、预览、存题库、发布。这中间有多少步、每一步调什么 tool、是否需要确认——**LLM 自己判断，不是开发者预设的分支。**

LangGraph 的 `create_react_agent` 提供这个能力：LLM 在一个 tool calling loop 里，每次 tool 执行完回到 LLM，LLM 自己决定继续调 tool 还是结束。`interrupt()` 让 LLM 能在"需要人确认"时暂停。

## Goals / Non-Goals

**Goals:**
- 用 `create_react_agent` 实现 LLM 自主决策的多步 tool calling
- `interrupt()` 嵌入 ReAct loop——LLM 判断需要确认时才停
- SSE 事件格式与现有前端 100% 兼容
- 新端点与旧端点并行，前端按需切换
- Gateway 分类器保留为 tool 预筛选

**Non-Goals:**
- 不写固定 workflow DAG——不预设"先 A 再 B 再 C"
- 不修改前端代码
- 不修改 tool 函数签名
- 不删除 pydantic-ai（保留为 fallback）
- Phase 1 不做 SQLite checkpointer（先 MemorySaver 验证）

## Architecture

### ReAct Agent Loop (create_react_agent)

```
用户消息 + system_prompt
       │
       ▼
┌──────────────────────────────────────┐
│          ReAct Agent Loop            │
│                                      │
│   ┌──────────┐     tool_call         │
│   │   LLM    │────────────────────→  │
│   │ (思考+决策)│                      │
│   │          │←────────────────────  │
│   └──────────┘     tool_result       │
│       │                              │
│       │ LLM 决定结束（不再调 tool）    │
│       ▼                              │
│   最终文本回复                         │
│                                      │
│   LLM 可随时:                          │
│   • 调 1 个 or 多个 tool               │
│   • 调同一个 tool 多次（不同参数）       │
│   • tool 失败 → 自己换策略              │
│   • 调 interrupt() → 等人确认          │
│   • 调完 search 发现不够 → 再调 generate │
└──────────────────────────────────────┘
       │
       ▼
   SSE 事件流 → 前端
```

### 不是这样的:

```
预设 DAG: classify → route → execute → extract
         LLM 没有选择权，路径是硬编码的
```

### 核心代码形态

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command

def create_chemai_agent(persona: str, provider: str):
    """创建 ChemAI ReAct agent。"""

    tools = get_tools_for_persona(persona)
    model = get_langchain_model(provider)
    system_prompt = build_persona_prompt(persona)

    # ReAct agent: LLM 在 tool calling loop 里
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
        checkpointer=MemorySaver(),
    )
    return agent
```

### interrupt() 的使用方式

不预设"到这个节点就暂停"。LLM 通过一个特殊的 `request_approval` tool 来表达"我需要确认"：

```python
async def request_approval(message: str, context: str = "") -> str:
    """向老师请求确认。当你生成内容后不确定是否需要调整，或者需要老师
    确认参数时调用。不要每步都调——只在真正需要人为判断时用。"""
    interrupt({
        "type": "approval_request",
        "message": message,
        "context": context,
    })
    # 老师回复后继续执行，interrupt() 返回老师的输入
    return "approved"
```

LLM 自己判断什么时候调 `request_approval`：
- 出完题了 → "老师请看看这 5 道题可以吗？" → interrupt
- 参数模糊 → 先调 `chemistry_tutor` 反问老师参数 → 不用 interrupt
- 搜真题结果太多 → 自己加筛选条件再搜 → 不用 interrupt

**interrupt 是一种 tool，LLM 可以选择调或不调。**

### SSE 事件流

`create_react_agent` 底层的 `astream_events()` 输出：

```
on_chain_start: LangGraph
  on_chat_model_start: LLM 开始思考
    on_chat_model_stream: token 流 (→ text SSE 事件)
    on_chat_model_stream: ...
  on_chat_model_end: LLM 结束输出
  on_tool_start: request_approval (→ interrupt 暂停)
  [等待前端发 Command(resume=...)]
  on_tool_end: request_approval result
  on_chat_model_start: LLM 恢复思考
    on_chat_model_stream: ...
  ...
  on_tool_start: generate_questions (→ tool_call SSE 事件)
  on_tool_end: generate_questions result (→ tool_result SSE 事件)
  ...
  on_chat_model_start: LLM 最终回复
    on_chat_model_stream: ...
on_chain_end: LangGraph 结束 (→ done SSE 事件)
```

**关键: `astream_events()` + `get_state()` 两阶段获取。** 流完成后从最终 state 读 messages，提取 tool_results 中的 `_route` 字段，发送 navigate/populate/action 事件。

### LangGraphSSEAdapter 设计

```python
class LangGraphSSEAdapter:
    """状态机：将 astream_events() 事件映射为 ChemAI SSE 事件。

    关键: 事件流结束后调用 graph.get_state(config) 读取最终状态，
    从 tool_results 中提取 _route 字段发送 navigate/populate/action。
    """

    def __init__(self):
        self._phase = "thinking"
        self._tool_results = []  # 收集 tool 结果用于 _route 提取

    def feed(self, event) -> list[str]:
        """处理单个 astream event，返回 SSE JSON 字符串列表。"""
        event_type = event.get("event")
        name = event.get("name", "")

        # LLM token 流
        if event_type == "on_chat_model_stream":
            results = []
            if self._phase != "reply":
                self._phase = "reply"
                results.append(json.dumps({"type": "phase", "phase": "reply"}))
            chunk = event["data"]["chunk"]
            if hasattr(chunk, "content") and chunk.content:
                results.append(json.dumps({"type": "text", "content": chunk.content}))
            return results

        # tool 开始执行
        if event_type == "on_tool_start":
            tool_name = name
            tool_input = event["data"].get("input", {})
            return [json.dumps({
                "type": "tool_call",
                "name": tool_name,
                "tool": _tool_category(tool_name),
                "args": _serialize_args(tool_input),
            })]

        # tool 执行完成
        if event_type == "on_tool_end":
            tool_name = name
            output = event["data"].get("output", "")
            result_str = str(output) if not isinstance(output, str) else output
            # 收集到 _tool_results 供最终 _route 提取
            try:
                parsed = json.loads(result_str)
                self._tool_results.append({
                    "tool_name": tool_name,
                    "result": parsed,
                })
            except json.JSONDecodeError:
                self._tool_results.append({
                    "tool_name": tool_name,
                    "result": {"raw": result_str[:500]},
                })
            # 解析 error 判断 success
            success = True
            try:
                data = json.loads(result_str)
                if isinstance(data, dict) and "error" in data:
                    success = False
            except (json.JSONDecodeError, TypeError):
                pass
            return [json.dumps({
                "type": "tool_result",
                "name": tool_name,
                "tool": _tool_category(tool_name),
                "success": success,
                "result": result_str[:8000],
            })]

        return []

    def finalize(self, final_state: dict) -> list[str]:
        """在 astream_events() 结束后调用，发送 route 事件 + done。"""
        events = []
        # 从 tool_results 读取 _route
        for tr in self._tool_results:
            route = tr.get("result", {}).get("_route")
            if route and route.get("navigate"):
                events.append(json.dumps({
                    "type": "navigate",
                    "page": route.get("page"),
                    "params": {},
                }))
                if route.get("populate"):
                    events.append(json.dumps({
                        "type": "populate",
                        "target": route["populate"]["target"],
                        "data": route["populate"]["data"],
                    }))
                for act in route.get("actions", []):
                    events.append(json.dumps({
                        "type": "action",
                        "action": act["action"],
                        "payload": act["payload"],
                    }))
                break  # 只用第一个触发导航的 tool
        events.append(json.dumps({"type": "done"}))
        events.append("[DONE]")
        return events
```

### Gateway 分类器的新角色

分类器不再是图的入口节点。改为作为 ReAct agent 的一个 tool：

```python
async def classify_intent(user_message: str) -> str:
    """分析用户意图，返回推荐的工具列表。Agent 可以用这个结果
    来缩小自己要选的 tool 范围，但不是必须——它可以自行决定。"""
    from agent.gateway import IntentClassifier
    from agent.provider.deepseek import get_classifier_provider

    classifier = IntentClassifier(get_classifier_provider())
    result = await classifier.classify(user_message)
    return json.dumps({
        "type": result.type,
        "recommended_tools": result.tools,
        "page": result.page,
    })
```

或者保持当前方案——在 agent 创建前跑分类器，把推荐的工具列表注入 system prompt:

```
system_prompt: 你是化学教研助手。
  用户说"{user_message}"。
  系统推荐工具: {recommended_tools}。
  你可以使用推荐的工具，也可以用其他工具。自己判断最合适的。
```

## Decisions

### D1: create_react_agent vs StateGraph

**选择**: `create_react_agent`（LangGraph 预置 ReAct agent）。

**理由**: LLM 自主决定 tool 调用顺序、次数和策略。不需要手工设计 `classify → route → execute` 这样的固定边。开发者只负责：给什么 tool、给什么 system prompt。

### D2: interrupt 策略

**选择**: `request_approval` 作为普通 tool 暴露给 LLM，tool 内部调 `interrupt()`。

**理由**: LLM 自己决定什么时候需要确认。不是"到节点 X 就停"。用 `interrupt()` 而非 `Command(resume)` 因为前者在 LangGraph 中自然映射到 checkpoint + 等待外部输入。

### D3: Gateway 分类器的位置

**选择**: 保留为前置筛选——在 agent 创建前跑分类器，结果注入 system prompt 的 tool 推荐列表。

**理由**: 分类器是优化（缩小候选 tool 集），不是控制（不允许 LLM 用其他 tool）。前置筛选减少 LLM 的选择负担，但 system prompt 明确说"你可以用推荐的工具，也可以用其他工具"。

### D4: 模型适配

**选择**: LangChain `ChatOpenAI` 适配所有 4 个 provider（DeepSeek/MiMo/Zhipu/DashScope）。

**理由**: `create_react_agent` 接受 LangChain BaseChatModel。ChatOpenAI 通过 base_url + api_key 接入所有 OpenAI 兼容 API。已验证通过。

### D5: 新端点策略

**选择**: 新增 `/api/agent/chat/langgraph/stream` + `/api/agent/chat/langgraph`，旧端点不变。

**理由**: 前端按需切换。旧 pydantic-ai 端点作为 fallback。

### D6: 中断恢复端点

**选择**: 新增 `POST /api/agent/chat/langgraph/resume`，接收 `conversation_id` + `user_response`，通过 `Command(resume=...)` 恢复被 interrupt 暂停的 graph。

**理由**: interrupt 暂停后，graph 状态保存在 MemorySaver 中。前端需要一种方式发送"老师点了确认"的响应来恢复执行。

### D7: session_id ↔ thread_id

**选择**: `conversation_id` 直接作为 LangGraph `thread_id`。

**理由**: LangGraph 的 MemorySaver 按 `thread_id` 隔离状态。1:1 映射避免维护两套 ID。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| ReAct agent 可能不调 tool 直接回答（闲聊场景） | system prompt 明确"教学任务优先调 tool"；GateWay 分类器推荐 tool 列表注入 prompt |
| LLM 可能过度调 `request_approval`→每步都问 | system prompt 写明"只在真正需要人为判断时调，不要每步都问" |
| interrupt 后 graph 等待，前端需要知道"在等人" | SSE 发送 `{"type": "phase", "phase": "awaiting_approval"}` 事件 |
| DeepSeek 的 tool calling 在 ChatOpenAI 下行为差异 | Phase 0 先验证 DeepSeek + ChatOpenAI bind_tools |
| `astream_events()` 的事件结构在 LangGraph 版本间可能变化 | 固定 langgraph==1.2.5 |
