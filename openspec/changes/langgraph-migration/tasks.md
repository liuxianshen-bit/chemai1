# LangGraph Agent — 开发任务

## Phase 0: 预验证

- [x] 0.1 `pip install langgraph langgraph-checkpoint langchain-core langchain-openai` ✅
- [x] 0.2 LangGraph 基础验证 ✅ (8/8, test_langgraph.py)
- [x] 0.3 DeepSeek + ChatOpenAI bind_tools + ReAct ✅ (4/4, test_langgraph_deepseek_tools.py)
- [x] 0.4 评估基线 ✅ (43/44 golden + 20/20 boundary + baseline_langgraph.json)
- [x] 0.5 确认当前可用 import 路径 ✅
  - `langgraph.prebuilt.create_react_agent` — 当前版本 (langgraph 1.2.5) 唯一可用路径
  - `langchain.agents.create_agent` 需 `langchain` 元包 (未安装)
  - 后续升级 langgraph 到位后再切换

## Phase 1: 核心 Agent 层

### 1.1 `agent/langgraph_agent.py` — ReAct Agent 工厂 ✅
> Spec: agent-react-loop

- [x] 1.1.1 实现 `get_tools_for_persona(persona)` — persona YAML → LangChain @tool 列表
- [x] 1.1.2 实现 `get_langchain_model(provider)` — ChatOpenAI 工厂 (in langgraph_agent.py)
- [x] 1.1.3 实现 `build_persona_prompt(persona, intent_hints)` — system prompt 构建
- [x] 1.1.4 实现 `create_chemai_agent(persona, provider, intent_hints="")` — agent 工厂
- [x] 1.1.5 实现 `request_approval` tool 函数 (via _make_request_approval_tool)
- [x] 1.1.6 实现 `requires_approval` tool 标记 (TOOL_APPROVAL_REQUIRED + metadata)

### 1.2 `agent/langgraph_sse.py` — SSE 适配器 ✅
> Spec: agent-sse-adapter

- [x] 1.2.1 实现 `_tool_category(name)` — 提取 tool 名前缀
- [x] 1.2.2 实现 `_serialize_args(tool_input)` — raw dict pass-through
- [x] 1.2.3 实现 `LangGraphSSEAdapter` 类 (feed + finalize + phase state)
- [x] 1.2.4 request_approval 过滤 (on_tool_start→phase:awaiting, on_tool_end→skip)
- [x] 1.2.5 _route 收集 (保存在 _tool_results, 用于 finalize)

### 1.3 `agent/channel/langgraph_channel.py` — FastAPI 端点 ✅
> Spec: agent-channel

- [x] 1.3.1 复用 `ChatRequest` 模型 + `_classify_and_narrow()`
- [x] 1.3.2 `POST /api/agent/chat/langgraph/stream` — SSE 流式
- [x] 1.3.3 Interrupt 检测 (双路径: except GraphInterrupt + get_state)
- [x] 1.3.4 `POST /api/agent/chat/langgraph/resume` — 中断恢复
- [x] 1.3.5 `POST /api/agent/chat/langgraph` — 非流式
- [x] 1.3.6 `POST /api/agent/chat/langgraph/reset` — 重置
- [x] 1.3.7 会话管理: conversation_id → thread_id

## Phase 2: 路由注册 + 模型适配 ✅

### 2.1 `agent/models.py` — LangChain 模型工厂 ✅
> Spec: agent-guardrails (Requirement: 模型工厂)

- [x] 2.1.1 新增 `get_langchain_model(provider) -> ChatOpenAI` (in langgraph_agent.py)

### 2.2 `app/main.py` — 路由注册 ✅
> Spec: agent-channel (Requirement: 旧端点兼容)

- [x] 2.2.1 `from agent.channel.langgraph_channel import router as langgraph_router`
- [x] 2.2.2 `app.include_router(langgraph_router, prefix="/api/agent")`

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
