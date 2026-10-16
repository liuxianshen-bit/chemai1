"""
调度器模块
使用APScheduler实现定时任务
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import timezone

scheduler = AsyncIOScheduler(timezone=timezone.utc)


def init_scheduler(app):
    """初始化调度器并注册任务"""
    from app.scheduler.daily_practice import daily_practice_job
    from app.scheduler.early_warning_check import check_warnings_job

    # 每日早上8点推送练习任务
    scheduler.add_job(
        daily_practice_job,
        CronTrigger(hour=8, minute=0),
        id='daily_practice',
        name='每日练习推送',
        replace_existing=True
    )

    # 每6小时检查一次预警
    scheduler.add_job(
        check_warnings_job,
        CronTrigger(hour=0, minute=0),
        id='check_warnings',
        name='学情预警检查',
        replace_existing=True
    )

    # OCR 答题卡轮询 (每5秒)
    from app.scheduler.ocr_scheduler import process_pending_ocr_tasks
    import asyncio as _asyncio
    async def _ocr_wrapper():
        await _asyncio.to_thread(process_pending_ocr_tasks)
    scheduler.add_job(
        _ocr_wrapper,
        trigger='interval',
        seconds=5,
        id='ocr_processor',
        name='OCR答题卡识别',
        replace_existing=True,
    )

    scheduler.start()
    print("调度器已启动")


def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown()
        print("调度器已关闭")
