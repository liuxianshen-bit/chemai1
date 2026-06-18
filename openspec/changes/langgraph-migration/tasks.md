# LangGraph Agent — 开发任务

## Phase 0: 预验证

- [x] 0.1 `pip install langgraph langgraph-checkpoint langchain-core langchain-openai` ✅
- [x] 0.2 LangGraph 基础验证 ✅ (8/8, test_langgraph.py)
- [x] 0.3 DeepSeek + ChatOpenAI bind_tools + ReAct ✅ (4/4, test_langgraph_deepseek_tools.py)
- [x] 0.4 评估基线 ✅ (43/44 golden + 20/20 boundary + baseline_langgraph.json)
- [ ] 0.5 `langchain.agents.create_agent` 正式路径验证 (替换 deprecated `create_react_agent`)
  - [ ] 更新 test_langgraph_deepseek_tools.py import
  - [ ] 重新跑 4 项测试确认行为一致
  - 验证: 4/4 PASS

## Phase 1: 核心 Agent 层

### 1.1 `agent/langgraph_agent.py` — ReAct Agent 工厂
> Spec: agent-react-loop

- [ ] 1.1.1 实现 `get_tools_for_persona(persona)` — persona YAML → LangChain @tool 列表
  - [ ] 用 `tool(fn)` 包装现有 async 函数 (不创建 per-tool wrapper)
  - [ ] 追加 `request_approval` tool
  - [ ] 返回值: `list[BaseTool]`
  - 验证: `get_tools_for_persona("tutor")` 返回 6+1=7 个 tool
- [ ] 1.1.2 实现 `get_langchain_model(provider)` — ChatOpenAI 工厂
  - [ ] deepseek/mimo/zhipu/dashscope 四个 provider
  - 验证: `model.ainvoke("hello")` 每个 provider 返回正常响应
- [ ] 1.1.3 实现 `build_persona_prompt(persona, intent_hints)` — system prompt 构建
  - [ ] 加载 persona YAML → system_prompt
  - [ ] 替换 `{student_profile}` 占位符
  - [ ] 如有 intent_hints, 追加 "## 工具推荐" 段落
  - 验证: prompt 包含 persona 名称、工具推荐、行为指引
- [ ] 1.1.4 实现 `create_chemai_agent(persona, provider, intent_hints="")` — agent 工厂
  - [ ] `from langchain.agents import create_agent`
  - [ ] `create_agent(model, tools, prompt, checkpointer=MemorySaver())`
  - [ ] 返回 CompiledGraph
  - 验证: `agent.ainvoke({"messages": [HumanMessage(content="你好")]})` 正常返回
- [ ] 1.1.5 实现 `request_approval` tool 函数
  - [ ] 签名: `async def request_approval(message: str, context: str = "") -> str`
  - [ ] 内部: `interrupt({"type": "approval", "message": message, "context": context})`
  - [ ] 返回: `"approved"` 或用户输入文本
  - [ ] description 写明 "只在真正需要人为判断时调用"
  - 验证: 函数可 import, `inspect.signature()` 正确
- [ ] 1.1.6 实现 `requires_approval` tool 标记与执行检查
  - [ ] 定义 `TOOL_APPROVAL_REQUIRED = {"assign_adaptive_practice", "import_exam_paper"}`
  - [ ] execute_tools 节点中: 调 marked tool 前检查是否已调过 request_approval
  - [ ] 未审批: 返回 error 而非执行
  - 验证: mock LLM 直接调 assign_adaptive_practice → tool 被阻止

### 1.2 `agent/langgraph_sse.py` — SSE 适配器
> Spec: agent-sse-adapter

- [ ] 1.2.1 实现 `_tool_category(name)` — 提取 tool 名前缀
  - [ ] `"generate_questions"` → `"generate"`
  - 验证: `_tool_category("search_exam_bank")` → `"search"`
- [ ] 1.2.2 实现 `_serialize_args(tool_input)` — raw dict pass-through
  - [ ] 直接返回 `tool_input` (dict)
  - 验证: `_serialize_args({"keyword": "test"})` → `{"keyword": "test"}`
- [ ] 1.2.3 实现 `LangGraphSSEAdapter` 类
  - [ ] `__init__()`: `_phase="thinking"`, `_tool_results=[]`
  - [ ] `feed(event) -> list[str]`:
    - `on_chat_model_stream` → text (首次前发 phase:reply)
    - `on_tool_start` → tool_call (request_approval → phase:awaiting_approval)
    - `on_tool_end` → tool_result (request_approval → skip)
    - 收集 tool_results (含 _route)
    - 其他 event → []
  - [ ] `finalize() -> list[str]`: route 事件 + done
  - 验证: mock astream events → 检查输出 SSE 格式
- [ ] 1.2.4 实现 _route 剥离逻辑
  - [ ] 在 `on_tool_end` 的 ToolMessage 传给 LLM 前: `result.pop("_route", None)`
  - [ ] 保留完整 result 在 `self._tool_results` 中
  - 验证: adapter._tool_results 含 _route, SSE tool_result 不含 _route
- [ ] 1.2.5 SSE 字段完整性验证
  - [ ] 对比旧 SSEAdapter 和新 LangGraphSSEAdapter 的输出
  - [ ] 逐事件类型检查必需字段
  - 验证: 所有 8 种事件类型字段匹配

### 1.3 `agent/channel/langgraph_channel.py` — FastAPI 端点
> Spec: agent-channel

- [ ] 1.3.1 复用 `ChatRequest` 模型 + `_classify_and_narrow()`
  - [ ] import from fastapi_sse
  - 验证: ChatRequest 解析正确
- [ ] 1.3.2 `POST /api/agent/chat/langgraph/stream` — SSE 流式
  - [ ] 加载 student profile (MemoryStack)
  - [ ] 跑分类器 → intent_hints; navigate → 快捷路径
  - [ ] 发送 `phase:thinking`
  - [ ] 创建 agent → `astream_events(msg, config, version="v2")` → adapter.feed() → yield
  - [ ] 流结束后: `finalize()` 发送 route 事件
  - [ ] try/except 包裹 → error SSE
  - 验证: curl 发送"出3道电化学选择题" → SSE 事件序列完整
- [ ] 1.3.3 Interrupt 检测 (双路径)
  - [ ] 路径 1: `except GraphInterrupt` → yield phase:awaiting_approval → return
  - [ ] 路径 2: `agent.get_state(config)` → 检查 state.next → yield phase:awaiting_approval
  - 验证: curl 发送"出5道题, 出完请我确认" → SSE 含 phase:awaiting_approval
- [ ] 1.3.4 `POST /api/agent/chat/langgraph/resume` — 中断恢复
  - [ ] 接收 conversation_id + user_response
  - [ ] `Command(resume=user_response)` + 同一 agent 实例
  - [ ] resume 流也调用 adapter.finalize()
  - 验证: interrupt → resume → SSE 正常完成 + route 事件
- [ ] 1.3.5 `POST /api/agent/chat/langgraph` — 非流式
  - [ ] `agent.ainvoke(msg, config)`
  - [ ] 提取最终文本 + route events
  - 验证: curl 非流式 → JSON 含 content + navigate 等
- [ ] 1.3.6 `POST /api/agent/chat/langgraph/reset` — 重置
  - [ ] 删除 thread checkpoint
  - 验证: reset 后新请求从空白对话开始
- [ ] 1.3.7 会话管理: conversation_id → thread_id
  - [ ] config = `{"configurable": {"thread_id": conversation_id}}`
  - [ ] memory_saver 自动持久化
  - 验证: 同一 conversation_id 连续 3 轮对话 → context 累积正确

## Phase 2: 路由注册 + 模型适配

### 2.1 `agent/models.py` — LangChain 模型工厂
> Spec: agent-guardrails (Requirement: 模型工厂)

- [ ] 2.1.1 新增 `get_langchain_model(provider) -> ChatOpenAI`
  - [ ] deepseek: model=deepseek-chat, base_url=api.deepseek.com/v1
  - [ ] mimo: model=mimo-v2.5, base_url=api.xiaomimimo.com/v1
  - [ ] zhipu: model=GLM-4-Flash, base_url=open.bigmodel.cn/api/paas/v4
  - [ ] dashscope: model=qwen-turbo, base_url=dashscope.aliyuncs.com/compatible-mode/v1
  - 验证: 四个 provider 各跑一次 `model.ainvoke("hi")`

### 2.2 `app/main.py` — 路由注册
> Spec: agent-channel (Requirement: 旧端点兼容)

- [ ] 2.2.1 `from agent.channel.langgraph_channel import router as langgraph_router`
- [ ] 2.2.2 `app.include_router(langgraph_router, prefix="/api/agent")`
- 验证: 启动 server, 新端点可访问

## Phase 3: 测试
> Spec: agent-guardrails (Requirement: Evals 断言覆盖)

- [ ] 3.1 跑 `agent_eval_golden.yaml` 所有场景 (LangGraph agent)
  - [ ] 16 个 pydantic-ai 兼容场景 + 7 个 LangGraph 特有场景
  - 验证: pydantic-ai 兼容场景通过率 >= 93% (1 个 fail 可接受: ambiguous-exam-request 应在新系统修复)
  - 验证: LangGraph 特有场景 7/7 PASS
- [ ] 3.2 边界/护栏 (20 项全部通过)
  - [ ] recursion_limit/requires_approval/dedup/SSE字段
  - 验证: 20/20 PASS
- [ ] 3.3 回归对比
  - [ ] 跑 `--regression` 对比 baseline_langgraph.json
  - [ ] tool 选择一致性 >= 93%
  - 验证: 无意外回归 (documented differences 除外)
- [ ] 3.4 手动端到端
  - [ ] curl 流式 → 检查 SSE 事件完整性
  - [ ] curl 非流式 → 检查 JSON 字段
  - [ ] interrupt → 前端不发 resume → 超时清理
  - [ ] 旧端点仍可工作

## Phase 4: 清理 + 文档

- [ ] 4.1 更新 `CLAUDE.md` — 加 LangGraph 开发指南
- [ ] 4.2 更新 `openspec/README.md` — 标记 langgraph-migration 完成
- [ ] 4.3 旧端点标注 deprecated (不删除), 记录在 CLAUDE.md

---

**总计: ~12 小时** (含测试和 debug)

**依赖关系:**
```
P0.5 (import 验证)
  → P1.1 (agent factory) + P1.2 (SSE adapter) [并行]
    → P1.3 (channel) → P2.1-2.2 (路由) [顺序]
      → P3 (测试) → P4 (文档)
```
