"""OCR and grading tools — answer sheet OCR progress, grading, and result saving."""

import json

from dotenv import load_dotenv
load_dotenv()


async def query_ocr_progress(teacher_id: str = "", batch_id: str = "") -> str:
    """答题卡识别进度 — 查询 OCR 识别任务的实时进度

    何时用：老师问"识别完了吗""进度怎么样了""答题卡识别进度"
    会发生什么：查询 ocr_tasks 表，返回每批每张答题卡的状态、百分比、学生信息
    下一步：全部完成后问老师是否要批改；部分失败可让老师重试
    NOT for 查批改结果 — 用 grade_answer_sheets"""
    from app.models.database import get_db
    from app.models.ocr_task import OCRTask

    db = next(get_db())
    try:
        q = db.query(OCRTask)
        if teacher_id:
            q = q.filter(OCRTask.teacher_id == teacher_id)
        if batch_id:
            q = q.filter(OCRTask.batch_id == batch_id)
        tasks = q.order_by(OCRTask.created_at.desc()).limit(30).all()

        batches = {}
        for t in tasks:
            bid = t.batch_id
            if bid not in batches:
                batches[bid] = {"total": 0, "done": 0, "failed": 0, "tasks": []}
            batches[bid]["total"] += 1
            if t.status == "done":
                batches[bid]["done"] += 1
            elif t.status == "failed":
                batches[bid]["failed"] += 1
            batches[bid]["tasks"].append(f"{t.title}: {t.status}({t.progress}%) {t.student_name or ''}")

        if not batches:
            return json.dumps({"message": "没有进行中的识别任务", "batches": {}}, ensure_ascii=False)

        summary_parts = []
        for bid, b in batches.items():
            pct = int(b["done"] / b["total"] * 100) if b["total"] else 0
            summary_parts.append(f"批次{bid}: {b['done']}/{b['total']}完成({pct}%), {b['failed']}失败")
            if b["tasks"]:
                summary_parts.append("  " + "; ".join(b["tasks"][:5]))

        all_done = all(b["done"] + b["failed"] == b["total"] for b in batches.values())
        return json.dumps({
            "summary": " | ".join(summary_parts),
            "all_done": all_done,
            "next_action": "全部识别完成，可开始批改" if all_done else "继续等待识别完成",
            "batches": batches,
        }, ensure_ascii=False)
    finally:
        db.close()


async def grade_answer_sheets(teacher_id: str = "", batch_id: str = "", exam_id: str = "") -> str:
    """答题卡批改 — 对已完成 OCR 识别的答题卡进行 LLM 批改

    何时用：OCR 识别全部完成后，老师说"开始批改""批改答题卡"
    会发生什么：对 batch 内所有 status=done 的任务跑 LLM 语义批改，返回逐学生结果
    下一步：展示结果卡片给老师，老师确认或修正后调 save_grading_results 保存
    NOT for 查识别进度 — 用 query_ocr_progress"""
    from app.models.database import get_db
    from app.models.ocr_task import OCRTask
    from app.services.llm_grading import grade_batch_answers

    db = next(get_db())
    try:
        tasks = db.query(OCRTask).filter(
            OCRTask.batch_id == batch_id,
            OCRTask.status == "done",
        ).all()

        if not tasks:
            return json.dumps({"error": "没有完成识别的答题卡", "batch_id": batch_id}, ensure_ascii=False)

        results = grade_batch_answers(tasks, correct_answers=None, exam_id=exam_id or None)

        grades_by_task = {r["task_id"]: r for r in results}
        for task in tasks:
            if task.task_id in grades_by_task:
                task.grading_result = grades_by_task[task.task_id]
        db.commit()

        summary = "\n".join(
            f"{r['student_name'] or r['task_id']}: {r['score']}/{r['total']}分"
            for r in results
        )
        return json.dumps({
            "message": f"批改完成，共{len(results)}份",
            "summary": summary, "results": results,
            "next_action": "请确认批改结果，确认后可保存",
        }, ensure_ascii=False)
    finally:
        db.close()


async def save_grading_results(teacher_id: str = "", batch_id: str = "") -> str:
    """保存批改结果 — 将确认后的批改结果写入学生答题记录并触发诊断

    何时用：老师确认批改结果后，说"保存""确认保存"
    会发生什么：逐学生写入 StudentAnswer 表，触发 LLM barrier 诊断
    下一步：返回班级统计和诊断结果
    NOT for 批改 — 用 grade_answer_sheets"""
    from app.models.database import get_db, StudentAnswer, Student
    from app.models.ocr_task import OCRTask

    db = next(get_db())
    try:
        tasks = db.query(OCRTask).filter(
            OCRTask.batch_id == batch_id,
            OCRTask.grading_result != None,
        ).all()

        saved = 0
        for task in tasks:
            task.confirmed = True
            sid = task.student_id
            if not sid or not task.grading_result:
                continue

            student = db.query(Student).filter(Student.student_id == sid).first()
            if not student:
                continue

            for q in task.grading_result.get("questions", []):
                db.add(StudentAnswer(
                    answer_id=f"ocr_{task.task_id}_{q['q_number']}",
                    student_id=sid,
                    question_id=f"ocr_{batch_id}_{q['q_number']}",
                    exam_record_id=batch_id,
                    student_answer=q.get("student_answer", ""),
                    is_correct=q.get("is_correct", False),
                ))
                student.exercises_completed = (student.exercises_completed or 0) + 1
            saved += 1
        db.commit()

        return json.dumps({
            "message": f"已保存 {saved}/{len(tasks)} 位学生的答题记录",
            "saved_count": saved, "total": len(tasks),
        }, ensure_ascii=False)
    finally:
        db.close()
