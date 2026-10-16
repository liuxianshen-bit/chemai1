"""APScheduler job for OCR task processing.

Polls ocr_tasks table every 5 seconds for pending tasks.
Processes one task at a time sequentially.
"""
import logging
from datetime import datetime
from app.services.ocr_mineru import get_ocr_provider

logger = logging.getLogger(__name__)


def process_pending_ocr_tasks():
    """Single job: find next pending task, process it, update result."""
    from app.models.database import get_db
    from app.models.ocr_task import OCRTask

    db = next(get_db())
    try:
        task = db.query(OCRTask).filter(
            OCRTask.status == "pending"
        ).order_by(OCRTask.created_at).first()

        if not task:
            return

        task.status = "processing"
        task.progress = 10
        db.commit()

        provider = get_ocr_provider()
        logger.info(f"OCR processing {task.task_id}: {task.image_path}")

        task.progress = 50
        db.commit()

        result = provider.extract(task.image_path)

        if result.get("error"):
            task.status = "failed"
            task.error_message = result["error"]
        else:
            task.status = "done"
            task.progress = 100
            task.student_id = result.get("student_id", "")
            task.student_name = result.get("student_name", "")
            task.ocr_result = {"answers": result.get("answers", [])}
            task.processed_at = datetime.utcnow()

        db.commit()
        logger.info(f"OCR {task.task_id}: {task.status} (sid={task.student_id}, name={task.student_name})")

    except Exception as e:
        logger.error(f"OCR scheduler error: {e}")
        try:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def start_ocr_scheduler(scheduler):
    """Register OCR job with existing APScheduler instance."""
    scheduler.add_job(
        process_pending_ocr_tasks,
        trigger="interval",
        seconds=5,
        id="ocr_processor",
        replace_existing=True,
    )
    logger.info("OCR scheduler started (5s interval)")
