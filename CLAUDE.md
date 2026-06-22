# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

## ChemAI 项目架构

### Agent 层 (LangGraph)

**新 Agent**: `agent/langgraph_agent.py` — LangGraph ReAct agent（替代 pydantic-ai 单轮调用）

```python
from agent.langgraph_agent import create_chemai_agent, GuardState

agent, guard_state = create_chemai_agent(persona="tutor", provider="deepseek")
result = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "你好"}]},
    config={"configurable": {"thread_id": "conv-123"}, "recursion_limit": 8},
)
```

**核心文件：**
- `agent/langgraph_agent.py` — Agent 工厂 + GuardState 护栏（去重 / requires_approval / _route 剥离）
- `agent/langgraph_sse.py` — astream_events → ChemAI SSE 事件格式适配器
- `agent/channel/langgraph_channel.py` — FastAPI 端点：`/api/agent/chat/langgraph/stream`、`/chat/langgraph`、`/chat/langgraph/resume`、`/chat/langgraph/reset`

**护栏 (D8/D9)：**
- `recursion_limit=8` — ReAct loop 最大迭代，通过 config 传入
- `GuardState` — per-invocation 共享状态：`seen_calls`（去重）、`approved`（requires_approval 检查）、`last_route`（_route 剥离后存储）
- 破坏性工具（`assign_adaptive_practice`, `import_exam_paper`）需要先调 `request_approval` 获得授权
- `_route` 字段在传给 LLM 前自动剥离

**端点：**
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent/chat/langgraph/stream` | POST | 流式 SSE |
| `/api/agent/chat/langgraph` | POST | 非流式 JSON |
| `/api/agent/chat/langgraph/resume` | POST | 中断恢复 |
| `/api/agent/chat/langgraph/reset` | POST | 重置对话 |

**旧端点 (deprecated, 保留为 fallback)：**
| 端点 | 说明 |
|------|------|
| `/api/agent/chat/stream` | pydantic-ai SSE（保留，计划 3 个月后下线） |
| `/api/agent/chat` | pydantic-ai 非流式（保留） |

### 测试

```bash
# 全部测试
python evals/test_langgraph_agent.py --all

# 单独模块
python evals/test_langgraph_agent.py --boundary   # 边界/护栏 (无 API)
python evals/test_langgraph_agent.py --golden     # Golden 数据集 (需 API)
python evals/test_langgraph_agent.py --langgraph  # LangGraph 特有场景 (需 API)
python evals/test_langgraph_agent.py --regression # 回归对比 (需 API)

# 完整测试套件
python evals/run_evals.py
```

### 已知架构缺口 (known_gaps)

这些是测试中发现的已知问题，详见 `evals/agent_eval_golden.yaml` 的 `known_gaps` 部分：

| 缺口 | 严重度 | 描述 |
|------|--------|------|
| search-exam-bank 不读 SQLite | **high** | `search_exam_bank` 只读 JSON 文件，Agent 保存到题库的题目无法被搜索到 |
| batch_import 方法缺失 | **high** | `import_exam_paper` 调用了不存在的 `ExamBankService.batch_import()` |
| 不自动保存题目 | medium | `generate_questions` 不自动保存，依赖 LLM 记得调 `save_to_bank` |
| LLM 跳过 approval | medium | 即使明确要求确认，LLM 仍有概率不调 `request_approval` |
| _route 不持久化 | low | _route 数据通过 SSE 传递，前端未打开时丢失 |

### 工作流完整性 (workflow_scenarios)

`evals/agent_eval_golden.yaml` 新增 5 个 workflow 场景，覆盖：
- 空知识点 → 必须反问
- 出题（无学生）→ 生成 → 保存 → 跳转
- 出题（有学生）→ 生成 → 不保存
- 搜索后信息不足 → 反问
- save_to_bank → 跳转题库 tab

**后续更新时务必跑 `--workflow` 测试确保这些场景不被回归。**