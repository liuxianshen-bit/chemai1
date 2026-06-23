# Inline Exam Workbench — 开发任务

## 1. Agent 工具替换
> Spec: inline-exam-component

- [ ] 1.1 在 `agent/tools.py` 中新增 `show_exam_workbench` 函数，返回 `_component` 指令
- [ ] 1.2 从 `TOOLS` 列表移除 `navigate_to_exam_workbench`，添加 `show_exam_workbench`
- [ ] 1.3 更新 `TOOL_PREREQUISITES`：`show_exam_workbench` 要求 `["knowledge_points", "question_types"]`
- [ ] 1.4 更新 `show_exam_workbench` 的 docstring 为 When/What/Next 格式
- [ ] 1.5 更新 persona YAML 的 `available_skills`：`navigate_to_exam_workbench` → `show_exam_workbench`

## 2. GuardState + SSE Adapter
> Spec: component-sse-event

- [ ] 2.1 `GuardState` 新增 `last_component` 字段
- [ ] 2.2 `_guarded` 包装器剥离 `_component` 并存入 `guard_state.last_component`
- [ ] 2.3 `LangGraphSSEAdapter.finalize()` 从 `guard_state.last_component` 发射 `component` SSE 事件
- [ ] 2.4 验证：工具返回 `_component` → GuardState 存储 → SSE 输出包含 `component` 事件

## 3. 前端内联面板
> Spec: component-sse-event (前端部分)

- [ ] 3.1 `agent.js` 新增 `component` SSE 事件处理
- [ ] 3.2 实现 `buildExamWorkbenchHTML(params)` — 生成参数摘要 + 操作按钮的 HTML
- [ ] 3.3 面板操作 JSON 导出：创建 HTML 的 `inline-exam-*` CSS class 命名空间 <br/> 样式按 exam-v2 风格（卡片、chip、按钮），独立隔离
- [ ] 3.4 实现面板"生成题目"按钮 → `POST /api/question/generate` → 题目渲染卡片<br/> 每道题有"编辑/保存/删除"操作按钮
- [ ] 3.5 实现"保存"调用 `POST /api/exam-bank/import-questions`
- [ ] 3.6 实现"完成"按钮关闭面板 + 发送总结消息

## 4. 测试

- [ ] 4.1 手动 E2E: 聊天出题 → Agent 反问收集参数 → 面板渲染 → 点击生成 → 题目展示 → 保存 → 关闭
- [ ] 4.2 验证：全程零页面跳转

---

**依赖关系:**
```
1 (agent tool) ─┐
                 ├→ 4 (testing)
2 (guard+sse) ──┤
                 │
3 (frontend) ───┘
```

1、2、3 可并行开发。
