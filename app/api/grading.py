"""Grading API — LLM batch grading + save + results.

POST /run — trigger LLM grading for a batch
POST /save — save confirmed results + trigger diagnosis
GET  /results/{batch_id} — get grading results
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from sqlalchemy.orm import Session
from app.models.database import get_db, StudentAnswer, Question, Student
from app.models.ocr_task import OCRTask
from app.services.llm_grading import grade_batch_answers

router = APIRouter()


@router.post("/run")
async def run_grading(
    batch_id: str = "",
    task_ids: Optional[list] = None,
    exam_id: str = "",
    correct_answers: Optional[list] = None,
    db: Session = Depends(get_db),
):
    """Trigger LLM grading for completed OCR tasks."""
    if batch_id:
        tasks = db.query(OCRTask).filter(
            OCRTask.batch_id == batch_id, OCRTask.status == "done"
        ).all()
    elif task_ids:
        tasks = db.query(OCRTask).filter(OCRTask.task_id.in_(task_ids)).all()
    else:
        raise HTTPException(status_code=400, detail="batch_id or task_ids required")

    if not tasks:
        raise HTTPException(status_code=404, detail="No completed OCR tasks found")

    results = grade_batch_answers(tasks, correct_answers, exam_id)

    # Store grading results on each task
    grades_by_task = {r["task_id"]: r for r in results}
    for task in tasks:
        if task.task_id in grades_by_task:
            task.grading_result = grades_by_task[task.task_id]
    db.commit()

    return {"success": True, "count": len(results), "results": results}


@router.post("/save")
async def save_grading(batch_id: str, db: Session = Depends(get_db)):
    """Save confirmed grading results to StudentAnswer + trigger diagnosis."""
    tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="Batch not found")

    saved = 0
    exam_record_id = batch_id  # use batch as exam record
    for task in tasks:
        if not task.grading_result or not task.confirmed:
            continue
        sid = task.student_id
        if not sid:
            continue
        # Ensure student exists
        student = db.query(Student).filter(Student.student_id == sid).first()
        if not student:
            continue

        for q in task.grading_result.get("questions", []):
            db.add(StudentAnswer(
                answer_id=f"ocr_{task.task_id}_{q['q_number']}",
                student_id=sid,
                question_id=f"ocr_{batch_id}_{q['q_number']}",
                exam_record_id=exam_record_id,
                student_answer=q.get("student_answer", ""),
                is_correct=q.get("is_correct", False),
            ))
        saved += 1
        # Trigger barrier diagnosis
        try:
            from app.api.diagnosis import run_llm_barrier_diagnosis
            await run_llm_barrier_diagnosis(exam_record_id=exam_record_id, db=db)
        except Exception:
            pass

    db.commit()
    return {"success": True, "saved_count": saved, "total": len(tasks)}


@router.get("/results/{batch_id}")
async def get_grading_results(batch_id: str, db: Session = Depends(get_db)):
    """Return grading results for a batch."""
    tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="Batch not found")

    results = []
    for t in tasks:
        results.append({
            "task_id": t.task_id,
            "title": t.title,
            "student_name": t.student_name,
            "student_id": t.student_id,
            "confirmed": t.confirmed,
            "grading_result": t.grading_result,
        })

    return {
        "success": True,
        "batch_id": batch_id,
        "results": results,
    }
