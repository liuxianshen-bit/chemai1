"""
每日练习自动推送任务
根据艾宾浩斯遗忘曲线为每个学生推送个性化的每日练习
"""

from datetime import datetime
from app.models.database import (
    Student, StudentParentBinding, ParentNotification,
    ExamRecord, get_db, RecordType
)
from app.models.review_task import ReviewTask
from app.services.notification_service import send_practice_notification


def daily_practice_job():
    """
    每日8点执行：
    1. 为每个学生生成/推送今日练习任务
    2. 为有绑定家长的学生发送通知到家长端
    3. 检查复习到期情况，发送复习提醒
    """
    db_gen = get_db()
    db = next(db_gen)

    try:
        # 获取所有学生
        students = db.query(Student).filter(Student.status == "approved").all()

        pushed_count = 0
        review_reminder_count = 0

        for student in students:
            # 为学生创建今日练习记录（如果还没有）
            practice = create_daily_practice(db, student)

            # 发送通知到学生端（通过标记new_practice）
            if practice:
                # 更新学生的 last_exercise_at
                student.last_exercise_at = datetime.utcnow()
                db.commit()

            # 如果有绑定家长，发送通知到家长端
            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student.student_id,
                StudentParentBinding.status == "active"
            ).all()

            for binding in bindings:
                # 发送练习通知
                notification = ParentNotification(
                    notification_id=f"daily_{student.student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                    parent_id=binding.parent_id,
                    student_id=student.student_id,
                    type="daily_report",
                    title=f"📝 {student.name} 今日练习已推送",
                    content=f"练习知识点：盐类水解、电离平衡等，请督促孩子完成",
                    is_read=False,
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                pushed_count += 1

                # 检查复习到期情况
                due_reviews = db.query(ReviewTask).filter(
                    ReviewTask.student_id == student.student_id,
                    ReviewTask.status.in_(["pending", "overdue"]),
                    ReviewTask.next_review_at <= datetime.utcnow()
                ).count()

                if due_reviews > 0:
                    review_notification = ParentNotification(
                        notification_id=f"review_{student.student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                        parent_id=binding.parent_id,
                        student_id=student.student_id,
                        type="reminder",
                        title=f"📚 {student.name} 有 {due_reviews} 道错题待复习",
                        content="请督促孩子完成复习任务",
                        is_read=False,
                        sent_at=datetime.utcnow()
                    )
                    db.add(review_notification)
                    review_reminder_count += 1

        db.commit()
        print(f"[每日推送] 已为 {len(students)} 名学生生成练习任务")
        print(f"[每日推送] 推送 {pushed_count} 条家长通知，{review_reminder_count} 条复习提醒")

    except Exception as e:
        print(f"[每日推送] 任务执行失败: {e}")
    finally:
        db.close()


def create_daily_practice(db, student):
    """
    为学生创建今日练习记录
    返回创建的练习记录
    """
    today = datetime.utcnow().date()

    # 检查今天是否已有练习
    existing = db.query(ExamRecord).filter(
        ExamRecord.class_id == student.class_id,
        ExamRecord.type == RecordType.PRACTICE,
        ExamRecord.exam_date >= datetime.combine(today, datetime.min.time())
    ).first()

    if existing:
        return existing

    # 创建新的每日练习
    practice_id = f"daily_{student.student_id}_{today.strftime('%Y%m%d')}"

    # 获取薄弱知识点（从学生的障碍类型推断）
    barrier_type = student.barrier_type or {}
    weak_kps = get_weak_knowledge_points(barrier_type)

    practice = ExamRecord(
        record_id=practice_id,
        class_id=student.class_id,
        type=RecordType.PRACTICE,
        name=f"每日练习 {today.strftime('%Y-%m-%d')}",
        question_stats={
            "knowledge_points": weak_kps,
            "question_count": 10,
            "difficulty": "medium",
            "target_barrier": get_dominant_barrier(barrier_type)
        },
        exam_date=datetime.combine(today, datetime.max.time()),
        source="DAILY_PRACTICE"
    )

    db.add(practice)
    db.commit()

    return practice


def get_weak_knowledge_points(barrier_type):
    """根据障碍类型返回应该练习的知识点"""
    # 简单实现：实际应该根据学生的错题历史来分析
    if isinstance(barrier_type, dict):
        if barrier_type.get("concept", 0) > 0.4:
            return ["盐类水解", "电离平衡", "水解平衡"]
        elif barrier_type.get("reading", 0) > 0.4:
            return ["化学实验设计", "题干分析技巧"]
        elif barrier_type.get("expression", 0) > 0.4:
            return ["化学用语规范", "表述练习"]
    return ["盐类水解", "电离平衡", "氧化还原反应"]


def get_dominant_barrier(barrier_type):
    """获取主要障碍类型"""
    if isinstance(barrier_type, dict):
        dominant = max(barrier_type, key=barrier_type.get)
        barrier_names = {
            "concept": "概念理解型",
            "reading": "审题障碍型",
            "expression": "表述障碍型"
        }
        return barrier_names.get(dominant, "概念理解型")
    return "概念理解型"
