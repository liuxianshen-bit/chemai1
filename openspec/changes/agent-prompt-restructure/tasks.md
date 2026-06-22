# Agent Prompt Restructure — 开发任务

## 1. Tool Docstrings 改写
> Spec: tool-docstring-context

- [ ] 1.1 改写 `search_exam_bank` docstring — 考试工作台 / 何时用 / 会发生什么 / 下一步
- [ ] 1.2 改写 `web_search` docstring
- [ ] 1.3 改写 `generate_questions` docstring — 含 save_to_bank 连锁提示；移除函数体内的空 kp 检查（改由 GuardState 统一处理）
- [ ] 1.4 改写 `diagnose_barrier` docstring
- [ ] 1.5 改写 `chemistry_tutor` docstring
- [ ] 1.6 改写 `simulate_experiment` docstring
- [ ] 1.7 改写 `balance_equation` docstring
- [ ] 1.8 改写 `weekly_report` docstring
- [ ] 1.9 改写 `import_exam_paper` docstring
- [ ] 1.10 改写 `assign_adaptive_practice` docstring
- [ ] 1.11 改写 `save_to_bank` docstring
- [ ] 1.12 验证：所有 11 个 docstring 包含"何时用：""会发生什么：""下一步："三个关键字

## 2. GuardState 前置条件 Gate
> Spec: tool-prerequisites

- [ ] 2.1 在 `agent/langgraph_agent.py` 中定义 `TOOL_PREREQUISITES` 字典（generate_questions: knowledge_points; diagnose_barrier/weekly_report/assign_adaptive_practice: student_id_or_class_id）
- [ ] 2.2 在 `GuardState` 类中实现 `check_prerequisites(name, kwargs) -> str|None`
- [ ] 2.3 在 `_make_guarded_tool` 的 `_guarded()` wrapper 中，最优先调用 `guard_state.check_prerequisites()`；通过后才继续 call limit/dedup 检查
- [ ] 2.4 验证：单元测试 — 空 kp 调用 generate_questions → 返回错误消息；有 kp → 正常执行

## 3. Prompt 结构化组装
> Spec: structured-prompt

- [ ] 3.1 实现 `_build_product_context()` — ChemAI 产品介绍（4 模块、用户类型、关键原则），约 200 字
- [ ] 3.2 实现 `_build_role_context(persona)` — 从 persona YAML system_prompt 提取角色定位，删除工具映射文字
- [ ] 3.3 实现 `_build_tool_context(tools)` — 遍历 StructuredTool.description，组装 [TOOLS] 段；跳过 request_approval 和格式不符的工具
- [ ] 3.4 实现 `_build_reasoning_anchor()` — 3 个自检问题
- [ ] 3.5 重写 `build_persona_prompt()` — 顺序组装 PRODUCT→ROLE→PROFILE→HINTS→REASONING→TOOLS，移除硬编码规则段
- [ ] 3.6 验证：调用 `build_persona_prompt("tutor")`，检查输出包含所有 4 个段且不包含"## 行为规则"

## 4. Persona YAML 清理
> Design: D5

- [ ] 4.1 清理 `tutor.yaml` system_prompt：保留"引导式教学"角色文本，删除工具映射 bullet list
- [ ] 4.2 清理 `teacher.yaml` system_prompt：保留角色上下文，删除工具映射
- [ ] 4.3 清理 `parent.yaml` system_prompt：保留角色描述，删除 JSON 决策格式指令

## 5. Evals 扩展
> Spec: all three — 补 workflow 场景和回归测试修复

- [ ] 5.1 新增 `wf-overcalling-search` 场景 — max_tool_calls: lte: 2
- [ ] 5.2 新增 `wf-persona-cross-teacher` 场景 — same input to teacher → diagnose_barrier
- [ ] 5.3 新增 `wf-persona-cross-parent` 场景 — same input to parent → weekly_report
- [ ] 5.4 新增 `wf-route-actions-complete` 场景 — route 含 actions 字段验证
- [ ] 5.5 新增 `wf-missing-info-blocked` 场景 — 空 kp 触发 GuardState block
- [ ] 5.6 修复回归测试：`test_regression_baseline` 加 `tool_trajectory_order` 比较；保存时区分 pydantic-ai 和 LangGraph baseline
- [ ] 5.7 在 `test_langgraph_agent.py` 的 run() 中注册 `--workflow` 标志（如未注册）

## 6. 测试与验证

- [ ] 6.1 跑 `--boundary` 验证护栏不受影响
- [ ] 6.2 跑 `--golden` 验证 golden 场景不回归（目标: >=97.7%）
- [ ] 6.3 跑 `--workflow` 验证新场景通过（目标: >=10/12）
- [ ] 6.4 跑 `--langgraph` 验证 LangGraph 特有场景不变
- [ ] 6.5 手动 E2E: curl LangGraph stream 端点，验证 SSE 事件完整（含 navigate/populate/action）

---

**依赖关系:**
```
1 (docstrings) ─┐
                 ├→ 3 (prompt) ─┐
2 (prerequisites)┘              ├→ 6 (testing)
                                │
4 (persona YAML) ──────────────┤
                                │
5 (evals) ─────────────────────┘
```

1、2、4、5 可并行。3 依赖 1+2。6 依赖全部。
