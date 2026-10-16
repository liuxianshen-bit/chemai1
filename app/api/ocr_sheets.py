"""Answer sheet upload & progress API.

POST /batch — multipart upload, returns task IDs
GET  /batch/{batch_id} — batch status + per-task progress
POST /{task_id}/retry — retry failed task
GET  / — teacher's task list
"""
import os, uuid, time
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.ocr_task import OCRTask

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "data", "answer_sheets")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/tasks/batch")
async def create_ocr_batch(
    teacher_id: str = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload a batch of answer sheet images. Returns batch_id + task_ids."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Max 10 files per batch")

    batch_id = f"batch_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    task_ids = []

    for i, f in enumerate(files):
        ext = os.path.splitext(f.filename or f"sheet_{i}.jpg")[1] or ".jpg"
        fname = f"{batch_id}_{i:03d}{ext}"
        fpath = os.path.join(UPLOAD_DIR, fname)
        content = await f.read()
        with open(fpath, "wb") as fh:
            fh.write(content)

        task_id = f"ocr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        task = OCRTask(
            task_id=task_id, teacher_id=teacher_id, batch_id=batch_id,
            image_path=fpath, title=f"答题卡_{i+1:02d}",
            created_at=datetime.utcnow(),
        )
        db.add(task)
        task_ids.append(task_id)
    db.commit()

    return {
        "success": True, "batch_id": batch_id, "task_ids": task_ids,
        "count": len(task_ids),
    }


@router.get("/tasks/batch/{batch_id}")
async def get_batch_status(batch_id: str, db: Session = Depends(get_db)):
    """Get status of all tasks in a batch."""
    tasks = db.query(OCRTask).filter(OCRTask.batch_id == batch_id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="Batch not found")

    task_list = []
    for t in tasks:
        task_list.append({
            "task_id": t.task_id, "title": t.title, "status": t.status,
            "progress": t.progress,
            "student_id": t.student_id,
            "student_name": t.student_name,
            "error": t.error_message,
            "confirmed": t.confirmed,
        })

    total = len(task_list)
    done = sum(1 for t in task_list if t["status"] == "done")
    failed = sum(1 for t in task_list if t["status"] == "failed")

    return {
        "success": True, "batch_id": batch_id, "total": total,
        "done": done, "failed": failed, "pending": total - done - failed,
        "tasks": task_list,
    }


@router.post("/tasks/{task_id}/retry")
async def retry_task(task_id: str, db: Session = Depends(get_db)):
    """Reset a failed task back to pending for retry."""
    task = db.query(OCRTask).filter(OCRTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "pending"
    task.progress = 0
    task.error_message = ""
    task.ocr_result = None
    db.commit()
    return {"success": True, "message": "Task reset to pending"}


@router.get("/tasks")
async def list_teacher_tasks(
    teacher_id: str = "",
    db: Session = Depends(get_db),
):
    """List tasks for a teacher, grouped by batch."""
    q = db.query(OCRTask)
    if teacher_id:
        q = q.filter(OCRTask.teacher_id == teacher_id)
    tasks = q.order_by(OCRTask.created_at.desc()).limit(100).all()

    batches = {}
    for t in tasks:
        if t.batch_id not in batches:
            batches[t.batch_id] = {"tasks": [], "created_at": str(t.created_at)}
        batches[t.batch_id]["tasks"].append({
            "task_id": t.task_id, "title": t.title, "status": t.status,
            "progress": t.progress, "student_name": t.student_name,
            "confirmed": t.confirmed,
        })

    return {"success": True, "batches": batches}
