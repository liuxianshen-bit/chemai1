# LangGraph Agent 迁移 — 任务分解

## Phase 0: 预验证

- [ ] 0.1 `pip install langgraph langgraph-checkpoint langchain-core` ✅ (已完成)
- [ ] 0.2 LangGraph 基础验证 ✅ (已完成, 8/8)
- [ ] 0.3 **新增** — DeepSeek + ChatOpenAI bind_tools 验证
  - [ ] 用 ChatOpenAI + deepseek-chat 调 bind_tools，确认 tool_call parsing 正确
  - [ ] 验证 `tool_choice="auto"` 行为: 闲聊时 LLM 可以不调 tool
  - [ ] 验证 ReAct loop: LLM → tool_call → tool_result → LLM 继续 → 结束
  - 测试脚本: `_temp/test_langgraph_deepseek_tools.py`

## Phase 1: 核心 Agent (3 个新文件)

### 1.1 `agent/langgraph_agent.py` — ReAct Agent 工厂 (60 min)

- [ ] `create_chemai_agent(persona, provider)` — 返回编译好的 ReAct agent
  - [ ] 加载 persona YAML → 获取 available_skills + system_prompt
  - [ ] `get_langchain_model(provider)` → ChatOpenAI 实例
  - [ ] `get_tools_for_persona(persona, tool_filter)` → LangChain @tool 列表
  - [ ] `create_react_agent(model, tools, prompt, checkpointer=MemorySaver())`
  - [ ] system_prompt 中注入 tool 推荐列表（来自 Gateway 分类器）
- [ ] 新增 `request_approval` tool
  - [ ] 接受 `message: str, context: str = ""` 参数
  - [ ] 内部调 `interrupt({"type": "approval", "message": message, "context": context})`
  - [ ] 返回值: `"approved"` 或用户输入文本
- [ ] 验证: `_temp/test_react_agent.py` — 用"帮我准备一份期中考试"跑 agent.invoke()

### 1.2 `agent/langgraph_sse.py` — SSE 适配器 (75 min)

- [ ] `LangGraphSSEAdapter` 类
  - [ ] `feed(astream_event) -> list[str]` — 事件 → SSE JSON 字符串列表
  - [ ] `finalize(final_state) -> list[str]` — 流结束后发送 route 事件 + done
  - [ ] 状态管理: `_phase` (thinking/reply), `_tool_results` (收集用于 _route)
- [ ] 事件映射（与现有 SSEAdapter 输出格式完全一致）:
  - [ ] `on_chat_model_start` → 无输出
  - [ ] `on_chat_model_stream` → `{"type":"text","content":chunk}` (首条前先发 `phase:reply`)
  - [ ] `on_tool_start` → `{"type":"tool_call","name":...,"tool":category,"args":...}`
  - [ ] `on_tool_end` → `{"type":"tool_result","name":...,"tool":category,"success":bool,"result":str}`
  - [ ] 过滤: 跳过 `request_approval` 的 tool_call/tool_result SSE 输出（改为 phase:awaiting_approval）
- [ ] interrupt 检测与通知
  - [ ] `on_tool_start` 为 `request_approval` → 发送 `{"type":"phase","phase":"awaiting_approval","message":...}`
- [ ] 验证: 用已知输入对比新旧 SSE 事件输出的字段和顺序

### 1.3 `agent/langgraph_channel.py` — FastAPI 端点 (90 min)

- [ ] 复用 `ChatRequest` 模型
- [ ] `POST /api/agent/chat/langgraph/stream` — SSE 流式端点
  - [ ] Phase: 加载 student profile → 跑 Gateway 分类器 → 创建 agent
  - [ ] 发送 `phase:thinking`
  - [ ] `agent.astream_events(msg, config, version="v2")` → `adapter.feed(event)` → yield SSE
  - [ ] Interrupt 检测: 如果 astream 遇到 `GraphInterrupt` → 返回当前状态 + `awaiting_approval` 标记
  - [ ] 流结束后: `agent.get_state(config)` → `adapter.finalize(state)` → yield 剩余事件
  - [ ] 异常处理: try/except 包裹 → yield error SSE → done
- [ ] `POST /api/agent/chat/langgraph` — 非流式端点
  - [ ] `agent.ainvoke(msg, config)` → 提取最终文本 + route events
  - [ ] 处理 Interrupt: 如果有 interrupt → 返回 interrupt 信息
- [ ] `POST /api/agent/chat/langgraph/resume` — 中断恢复端点
  - [ ] 接收 `conversation_id` + `user_response`
  - [ ] `agent.ainvoke(Command(resume=user_response), config)` → 继续执行
  - [ ] 返回流式或非流式结果
- [ ] `POST /api/agent/chat/langgraph/reset` — 重置对话
- [ ] 会话: `conversation_id` → `thread_id`，复用 `_conversations` 或独立 MemorySaver
- [ ] 验证: curl 流式端点，检查 SSE 事件序列和字段完整性

## Phase 2: 适配层 (原地修改)

### 2.1 `agent/models.py` — LangChain 模型工厂 (15 min)

- [ ] 新增 `get_langchain_model(provider: str) -> ChatOpenAI`
  - [ ] deepseek: base_url=https://api.deepseek.com/v1, model=deepseek-chat
  - [ ] mimo: base_url=https://api.xiaomimimo.com/v1, model=mimo-v2.5
  - [ ] zhipu: base_url=https://open.bigmodel.cn/api/paas/v4, model=GLM-4-Flash
  - [ ] dashscope: base_url=https://dashscope.aliyuncs.com/compatible-mode/v1, model=qwen-turbo
- [ ] 验证: 四个 provider 各跑一次 `model.ainvoke("hello")`

### 2.2 `agent/tools.py` — 工具包装 (20 min)

- [ ] 保留所有现有函数不变
- [ ] 新增 `get_tools_for_persona(persona: str, tool_filter: list[str] | None) -> list`
  - [ ] 读取 persona YAML → available_skills
  - [ ] 如果 tool_filter 非空 → 取交集；空交集 → 全量
  - [ ] 返回 `[tool(fn) for fn in TOOLS if fn.__name__ in skills]`
- [ ] 注意: LangChain `@tool` 可以直接包装现有 async 函数，不需要 per-tool wrapper
- [ ] 新增 `request_approval` 函数（见 1.1）
- [ ] 验证: `get_tools_for_persona("tutor", None)` 返回 6 个 LangChain tools

### 2.3 `app/main.py` — 路由注册 (2 min)

- [ ] `from agent.channel.langgraph_channel import router as langgraph_router`
- [ ] `app.include_router(langgraph_router, prefix="/api/agent")`

### 2.4 `agent/gateway.py` — 分类器集成 (10 min)

- [ ] 新增辅助函数 `classify_and_get_tools(message, persona, message_history) -> list[str] | None`
  - [ ] 调用 IntentClassifier.classify()
  - [ ] 如果 type=navigate → 返回特殊标记
  - [ ] 否则返回 tool 推荐列表
- [ ] 不变: 分类器本身、prompt、keyword fallback 全部保持

## Phase 3: Tool 增强 (为 agent 决策提供更多上下文)

### 3.1 `request_approval` tool (10 min)

- [ ] 实现 `async def request_approval(message: str, context: str = "") -> str`
  - [ ] 调 `interrupt({"type": "approval", "message": message, "context": context})`
  - [ ] 返回用户输入或 "approved"
- [ ] 加到 `TOOLS` 列表

### 3.2 替换 tool (5 min)

- [ ] 什么都不用改。`generate_questions` 出完题返回 JSON 含 `_route`，
  LLM 看到结果后自己决定调 `request_approval` 给老师预览，还是直接继续。

## Phase 4: 测试

### 4.1 `evals/test_langgraph_agent.py` — Agent 行为测试 (60 min)

- [ ] ReAct loop 测试: "帮我准备一份期中考试" → 观察到 LLM 调了多个 tool
- [ ] Self-correction 测试: 故意让 tool 返回 error → LLM 重试
- [ ] Interrupt 测试: LLM 调 request_approval → 验证 interrupt 触发
- [ ] Resume 测试: Command(resume="approved") → 验证继续执行
- [ ] tool_choice 正确性: "你好" → 不调 tool
- [ ] SSE 事件格式对比: 新旧端点输出 diff

### 4.2 `evals/test_gateway_router.py` — 不作改动

- 现有测试全部通过（分类器逻辑未变）

### 4.3 `evals/test_unit_tools.py` — 不作改动

- 工具函数签名不变

### 4.4 `evals/test_classifier.py` — 不作改动

- 分类器逻辑未变

### 4.5 `evals/test_sse_streaming.py` — 适配

- [ ] 替换 `run_agent_test()` 为 LangGraph 版
- [ ] SSE 事件序列断言保持

## Phase 5: 清理 & 文档

### 5.1 文档 (15 min)

- [ ] `docs/langgraph-agent-architecture.md` — 架构说明（ReAct loop, interrupt, SSE 适配）
- [ ] 更新 `CLAUDE.md` — 添加 LangGraph 开发指南
- [ ] 更新 `openspec/README.md` — 标记迁移状态

### 5.2 旧代码（Phase 5, 所有测试通过后）

- [ ] 不急于删除。旧 pydantic-ai 端点作为 fallback 保留至少 1 个月。

---

**总计: ~6 小时**

**依赖关系:**
```
Phase 0 (预验证)
  → Phase 1 (核心 agent) [1.1 → 1.2 → 1.3]
    → Phase 2 (适配) [全部可并行]
      → Phase 3 (tool 增强) [可并行]
        → Phase 4 (测试) [4.1, 4.5]
          → Phase 5 (文档)
```
