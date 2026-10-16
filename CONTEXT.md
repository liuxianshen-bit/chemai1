# ChemAI — Domain Glossary

The shared vocabulary for the ChemAI AI-assisted chemistry teaching tool. No implementation details — this is a glossary of what things _are_, not how they're built.

---

## Core Entities

- **Student (学生)**: A learner enrolled in a class. Has a barrier profile (concept/reading/expression distribution) derived from error analysis.
- **Class (班级)**: A group of students taught by a teacher. Identified by name (e.g. "高一(1)班"). Has exam history and aggregated learning analytics.
- **Teacher (教师)**: An instructor who manages classes, reviews diagnostics, assigns practice.
- **Parent (家长)**: A guardian who receives learning reports for their child.

## Learning Concepts

- **Barrier Type (障碍类型)**: The root cause behind a student's mistakes. Three categories (stored as lowercase strings in DB, enforced by `BarrierType(str, Enum)` in Python):
  - `concept` (概念理解障碍): Doesn't understand the underlying chemistry concept.
  - `reading` (审题障碍): Misreads the question or falls for traps.
  - `expression` (表述障碍): Understands the concept but can't express the answer properly.
- **Barrier Distribution (障碍分布)**: A per-student ratio across the three barrier types, e.g. `{concept: 0.3, reading: 0.5, expression: 0.2}`. The dominant barrier is the highest-valued one.
- **Knowledge Point (知识点)**: An atomic chemistry topic (e.g. "盐类水解", "氧化还原反应"). Questions are tagged with knowledge points. Error rates are tracked per knowledge point per class.
- **Diagnosis (诊断)**: The act of determining a student's barrier profile from their error history. Can be individual (one student) or class-level (aggregate distribution).
- **Adaptive Practice (自适应练习)**: Personalized exercises generated based on a student's barrier type and weak knowledge points. Targets the zone of proximal development.

## Content Entities

- **Exam Paper (试卷)**: A sourced set of chemistry questions (e.g. "2024 湖南高考"). Has year, region, source.
- **Question (题目)**: An individual chemistry problem. Has content, options, answer, knowledge points, difficulty.
- **Question Set / Bank (题库)**: A named collection of questions, typically AI-generated and saved for reuse. Has a set_id, name, and question count.
- **Weekly Report (周报)**: A learning summary generated for a student or class, covering recent practice, progress, and suggestions.

## Question & Exam Concepts

- **Question Type (题目类型)**: The format of a chemistry problem. Canonical enum (backend):
  - `single_choice` / `multi_choice` — 单选/多选题
  - `true_false` — 判断题
  - `fill_blank` — 填空题
  - `short_answer` — 简答题
  - `essay` — 论述题
  - `calculation` — 计算题
  - `experiment` — 实验题
  - Frontend TypeScript maps to these with lower_snake_case. Frontend API may use shortened aliases (`choice`→`single_choice`) for user-facing labels, but the wire format is always the canonical enum.
- **Difficulty (难度)**: Integer 1–5 scale. 1=基础, 2=中等偏易, 3=中等, 4=较难, 5=竞赛/拔高。后端存储为Integer，前端API传输为integer。不使用字符串标签。
- **Four-Dimension Review (四维审核)**: AI quality check for AI-generated *questions*. Four dimensions:
  - **Scientific Accuracy** (科学性) — Is the chemistry correct?
  - **Difficulty Match** (难度匹配) — Does it match target difficulty (1–5)?
  - **Knowledge Point Coverage** (知识点覆盖) — Does it test the claimed knowledge points?
  - **Discrimination** (区分度) — Can it separate strong and weak students?
  Each scored 0–100, composite = weighted sum (科学性×0.4 + 难度×0.25 + 知识×0.2 + 区分×0.15).
  Note: Part 4 also defines a separate **Chemical Equation Four-Dimension Verification (化学方程式四维校验)** for auditing chemical equation *correctness* (系数配平/反应条件/产物正确性/结构正确性). Despite the similar name, these are different systems for different artifacts.
- **Exam State (考试状态)**: The lifecycle of an exam. States: `draft → published → in_progress → grading → completed → archived` (+ `cancelled` from any non-terminal state). Each transition records a timestamp.

- **Type Mapping (类型映射表)**: The same `question_type` travels across three layers with different representations. This is intentional (each layer has different constraints), but the mapping MUST be followed at API boundaries:

| Layer | Example value | Notes |
|-------|-------------|-------|
| Backend (Python/SQLAlchemy) | `single_choice` | Canonical enum. Stored in DB. All API validation uses this. |
| Frontend API (TypeScript wire) | `single_choice` | Matches backend exactly — no transformation at the API boundary |
| Frontend UI label | `单选题` | Display only. Never sent to backend. |
| Doc 25 TypeScript enum | `SINGLE_CHOICE` | TS enum convention (UPPER_SNAKE). Map to backend string via `QuestionType[value].toLowerCase()` |
| Part 4 design docs | `choice` | Shorthand used in design docs only. Maps to `single_choice` |

| Backend (canonical) | TS Enum | UI Label | Part 4 shorthand |
|---------------------|---------|----------|-------------------|
| `single_choice` | `SINGLE_CHOICE` | 单选题 | `choice` |
| `multi_choice` | `MULTI_CHOICE` | 多选题 | — |
| `true_false` | `TRUE_FALSE` | 判断题 | — |
| `fill_blank` | `FILL_BLANK` | 填空题 | `fill` |
| `short_answer` | `SHORT_ANSWER` | 简答题 | — |
| `essay` | `ESSAY` | 论述题 | — |
| `calculation` | `CALCULATION` | 计算题 | `calc` |
| `experiment` | `EXPERIMENT` | 实验题 | `experiment` |

## Diagnosis Concepts

- **Misconception Category (迷思概念类别)**: The chemistry *topic domain* where a student's error lies. Six categories: 化学平衡 (Chemical Equilibrium), 氧化还原 (Redox), 摩尔计算 (Stoichiometry), 有机化学 (Organic Chemistry), 化学用语 (Chemical Notation), 物构知识 (Structure & Properties). Used by the rule engine (doc 27) to classify errors by subject area.
- **Barrier Type vs Misconception Category**: These are ORTHOGONAL dimensions — Barrier Type (概念/审题/表述) answers *how* the student errs (pedagogical root cause). Misconception Category answers *where* the student errs (chemistry subject area). A single error has both: e.g. "概念理解障碍 in 化学平衡".

## Agent Concepts

- **Intent (意图)**: What the user wants. Two types: `chat` (needs tool execution) or `navigate` (pure page open). Classified by the Gateway (LLM + keyword fallback).
- **Single Agent (单Agent)**: A LangGraph ReAct agent (`create_react_agent`) with all persona-filtered tools visible. The LLM selects tools based on their docstring descriptions — no routing layers. (v2 architecture; v1 multi-agent kept as fallback.)
- **Tool (工具)**: A callable function exposed to the Agent. Each tool has a docstring in "何时用 / 会发生什么 / 下一步 / NOT for" format. Tool descriptions are the sole interface for tool selection — the LLM reads them and decides which to call.
- **Persona (角色)**: Determines which tools are available. Four personas: `tutor` (学生端AI辅导, ~7 tools), `teacher` (教师端教研助手, ~18 tools), `parent` (家长端报告查看, ~2 tools), `admin` (系统管理, ~3 tools). Defined in `agent/personas/*.yaml`. Tools register their Persona membership via TOOL_META. At runtime, `langgraph_agent_v2.py` filters the tool list to only those matching the active Persona.
- **Guard State (护栏状态)**: Per-invocation shared state tracking deduplication, call limits, and approval status for destructive tools. Wraps every tool via `_make_guarded_tool`.
- **Gateway (网关)**: Pre-classifier that runs before the Agent. Outputs intent type (chat/navigate) and suggested tools. Navigate intents short-circuit the Agent entirely. Chat intents proceed to the ReAct loop with tool hints.

## OCR Pipeline Concepts

- **Upload Session (上传会话)**: Tracks a file from upload through preview to final processing. States: UPLOADED → PREVIEWING → READY → IMPORTING/GRADING → IMPORTED/GRADED → DONE. Persisted in SQLite.
- **Preview (预览)**: Fast, synchronous OCR using `doc_analysis` to show the user what's in their file before they commit to an expensive async operation.
- **Exam Import (试卷导入)**: Uses `paper_cut_edu_vlm` (async, multimodal) to segment and extract question text from exam paper images. The only path for building the question bank from PDFs/images.
- **Grading (判卷)**: Uses `correct_edu` (async) to grade student answer sheets against answer keys. Returns per-question correct/incorrect, reasons, and annotated images.
- **Fallback (降级)**: When a multimodal API fails, the system falls back to `doc_analysis` (sync OCR) as a degraded but functional alternative. Users are informed of degraded quality.
- **Task Polling (任务轮询)**: Async operations (import, grading) use client-side polling: the server returns a task_id immediately and the frontend polls `GET /api/ocr/tasks/{upload_id}/status` every 2 seconds for progress.
- **Formula Result (公式结果)**: LaTeX-format chemical formulas returned by `doc_analysis`. Preview saves these; import reuses them as hints to the LLM for higher-accuracy structuring.
- **Student Submission (学生作答)**: A student's completed answer sheet, stored with original image, graded image, per-question results, and total score. Belongs to an Exam.
- **Exam (考试)**: A named assessment event (e.g. "2024期中考试") belonging to a Class, containing student submissions and associated questions.
