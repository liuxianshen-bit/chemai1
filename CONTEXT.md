# ChemAI — Domain Glossary

The shared vocabulary for the ChemAI AI-assisted chemistry teaching tool. No implementation details — this is a glossary of what things _are_, not how they're built.

---

## Core Entities

- **Student (学生)**: A learner enrolled in a class. Has a barrier profile (concept/reading/expression distribution) derived from error analysis.
- **Class (班级)**: A group of students taught by a teacher. Identified by name (e.g. "高一(1)班"). Has exam history and aggregated learning analytics.
- **Teacher (教师)**: An instructor who manages classes, reviews diagnostics, assigns practice.
- **Parent (家长)**: A guardian who receives learning reports for their child.

## Learning Concepts

- **Barrier Type (障碍类型)**: The root cause behind a student's mistakes. Three categories:
  - **Concept (概念理解障碍)**: Doesn't understand the underlying chemistry concept.
  - **Reading (审题障碍)**: Misreads the question or falls for traps.
  - **Expression (表述障碍)**: Understands the concept but can't express the answer properly.
- **Barrier Distribution (障碍分布)**: A per-student ratio across the three barrier types, e.g. `{concept: 0.3, reading: 0.5, expression: 0.2}`. The dominant barrier is the highest-valued one.
- **Knowledge Point (知识点)**: An atomic chemistry topic (e.g. "盐类水解", "氧化还原反应"). Questions are tagged with knowledge points. Error rates are tracked per knowledge point per class.
- **Diagnosis (诊断)**: The act of determining a student's barrier profile from their error history. Can be individual (one student) or class-level (aggregate distribution).
- **Adaptive Practice (自适应练习)**: Personalized exercises generated based on a student's barrier type and weak knowledge points. Targets the zone of proximal development.

## Content Entities

- **Exam Paper (试卷)**: A sourced set of chemistry questions (e.g. "2024 湖南高考"). Has year, region, source.
- **Question (题目)**: An individual chemistry problem. Has content, options, answer, knowledge points, difficulty.
- **Question Set / Bank (题库)**: A named collection of questions, typically AI-generated and saved for reuse. Has a set_id, name, and question count.
- **Weekly Report (周报)**: A learning summary generated for a student or class, covering recent practice, progress, and suggestions.

## Agent Concepts

- **Intent (意图)**: What the user wants. Two types: `chat` (needs tool execution) or `navigate` (pure page open). Classified by the Gateway (LLM + keyword fallback).
- **Single Agent (单Agent)**: A LangGraph ReAct agent (`create_react_agent`) with all persona-filtered tools visible. The LLM selects tools based on their docstring descriptions — no routing layers. (v2 architecture; v1 multi-agent kept as fallback.)
- **Tool (工具)**: A callable function exposed to the Agent. Each tool has a docstring in "何时用 / 会发生什么 / 下一步 / NOT for" format. Tool descriptions are the sole interface for tool selection — the LLM reads them and decides which to call.
- **Persona (角色)**: Determines which tools are available. Three personas: tutor (student-facing, 6 tools), teacher (8 tools including diagnosis), parent (2 tools: weekly_report, diagnose_barrier). Defined in `agent/personas/*.yaml`.
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
