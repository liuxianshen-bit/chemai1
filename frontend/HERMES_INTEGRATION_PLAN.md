# Hermes Agent 集成实施计划

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                                │
│                     teacher_v2.html                            │
│                     student_v2.html                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Hermes Agent (ReAct循环)                      │
│                    localhost:8642                             │
│                                                              │
│  Skill 调用链：                                              │
│  ├── chemistry_parser  ← MinerU 集成！                      │
│  │   └── parse_pdf_questions()  ← PDF解析                   │
│  ├── chemistry_exam                                          │
│  │   ├── exam_ocr_recognize()  ← OCR识别                  │
│  │   ├── exam_generate()  ← AI出题                         │
│  │   ├── exam_import_questions()  ← 导入真题                │
│  │   └── exam_search_historical()  ← 真题库检索            │
│  └── chemistry_diagnosis                                     │
│      ├── diagnosis_barrier_class()  ← 障碍诊断              │
│      └── diagnosis_plan_generate()  ← 学习计划               │
└─────────────────────────────────────────────────────────────┘
```

---

## 已完成

### 1. Hermes Agent Service ✅
- [x] `src/services/hermes.js` - Hermes Agent Service 核心实现
  - SSE 事件流解析
  - HITL 确认/修正机制
  - TaskType 定义
  - ConfirmType 定义

### 2. Hermes Thinking 展示组件 ✅
- [x] `src/components/HermesThinking.js` - 真正的流式 Agent 思考展示
  - 支持 thinking、tool_call、tool_result 事件展示
  - 支持 needs_confirmation 确认弹窗
  - 工具图标和名称映射
  - 取消和确认按钮

### 3. Hermes UI 工具 ✅
- [x] `src/utils/hermes-ui.js` - 流式调用包装工具
  - runHermesTask() - 带 UI 反馈的执行
  - 阶段性消息自动更新
  - 日志展示

### 4. 教师端模块对接 ✅

| 功能 | 模块文件 | 状态 |
|------|----------|------|
| OCR识别 | `src/modules/teacher/ocr.js` | ✅ 已重构，使用 Hermes Agent |
| AI出题 | `src/modules/teacher/question.js` | ✅ 已重构，使用 Hermes Agent |
| 障碍诊断 | `src/modules/teacher/diagnosis.js` | ✅ 已重构，使用 Hermes Agent |
| 学习计划生成 | `src/modules/teacher/diagnosis.js` | ✅ 已重构，使用 Hermes Agent |
| 学习计划应用 | `src/modules/teacher/diagnosis.js` | ✅ 已对接 |

### 5. HTML 结构 ✅
- [x] `teacher_v2.html` - 完整的模态框和页面结构
- [x] `student_v2.html` - 学生端页面结构（已存在）

---

## 待实施任务

### 1. 学生端模块对接（部分完成）

| 功能 | 模块文件 | 状态 |
|------|----------|------|
| 学习任务展示 | `src/modules/student/home.js` | 待对接 |
| 练习答题 | `src/modules/student/practice.js` | 待对接 |
| 学习计划查看 | `src/modules/student/learning_plan.js` | ✅ 已实现 |
| 学情报告 | `src/modules/student/report.js` | 待对接 |

### 2. 服务端
- [ ] 启动 Hermes Agent 服务（`python gateway/platforms/api_server.py`）
- [ ] 验证 SSE 流式事件正确返回

---

## Hermes Agent SSE 事件类型

```javascript
// 事件流示例
{ "type": "thinking", "content": "分析图片内容..." }
{ "type": "tool_call", "tool": "exam_ocr_recognize", "params": {...} }
{ "type": "tool_result", "confidence": 0.85 }
{ "type": "needs_confirmation", "confirm_type": "ocr_preview", "data": {...} }
{ "type": "confirmed", "corrections": {"5": "C"} }
{ "type": "final", "result": {...} }
```

---

## TaskType 任务类型

| Task | 对应Skill | 功能 |
|------|----------|------|
| `TaskType.OCR_RECOGNIZE` | chemistry_exam | OCR识别答题卡 |
| `TaskType.PDF_PARSE` | chemistry_parser | MinerU解析PDF |
| `TaskType.GENERATE_QUESTIONS` | chemistry_exam | AI出题 |
| `TaskType.IMPORT_QUESTIONS` | chemistry_exam | 导入真题 |
| `TaskType.ANALYZE_BARRIER` | chemistry_diagnosis | 障碍诊断 |
| `TaskType.GENERATE_LEARNING_PLAN` | chemistry_diagnosis | 学习计划 |
| `TaskType.GENERATE_REPORT` | chemistry_diagnosis | 学情报告 |

---

## 使用示例

### 1. OCR识别

```javascript
import { hermesService, TaskType } from '@/services'
import { showHermesThinking, hideHermesThinking } from '@/components'

// 显示流式界面
showHermesThinking({
  task: TaskType.OCR_RECOGNIZE,
  message: '正在识别答题卡...',
  onCancel: () => hermesService.cancel()
})

// 执行流式任务
const streamResult = hermesService.executeStream(TaskType.OCR_RECOGNIZE, {
  image: base64Data,
  questions: [...]
})

hermesService.processStream(streamResult.reader, (event) => {
  // 事件会在回调中处理
  switch (event.type) {
    case 'thinking':
      // 更新 thinking 内容展示
      break
    case 'tool_call':
      // 展示工具调用
      break
    case 'tool_result':
      // 展示工具结果
      break
    case 'needs_confirmation':
      // 显示确认弹窗
      break
    case 'final':
      // 任务完成
      hideHermesThinking()
      break
  }
})
```

### 2. AI出题

```javascript
hermesService.executeStream(TaskType.GENERATE_QUESTIONS, {
  knowledge_points: ['氧化还原反应', '电化学'],
  difficulty: 'medium',
  quantity: 10,
  exam_type: '单元练习'
})
```

### 3. 学习计划

```javascript
hermesService.executeStream(TaskType.GENERATE_LEARNING_PLAN, {
  student_id: 'stu_001',
  barrier_type: 'concept',
  weak_knowledge_points: ['氧化还原反应概念', '化合价变化']
})
```

---

## HITL 修正类型

| 修正类型 | action | 说明 |
|---------|--------|------|
| 直接修改 | `modify` | 用户手动输入正确值 |
| 重试 | `retry` | 点击重新识别 |
| 跳过 | `skip` | 跳过该题 |
| 手动输入 | `manual` | 切换人工模式 |
| 终止 | `abort` | 取消任务 |

---

## 启动 Hermes Agent

```bash
cd D:\化学\hermes-agent-main
python gateway/platforms/api_server.py
```

服务地址：`http://localhost:8642/v1`

---

## 下一步

1. 启动 Hermes Agent 服务
2. 测试完整流程：
   - OCR 识别（SSE 流式）
   - AI 出题（SSE 流式）
   - 障碍诊断（SSE 流式）
   - 学习计划生成（SSE 流式）
3. 学生端模块对接
