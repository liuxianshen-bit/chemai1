"""
通知服务
处理APP内通知（家长端消息、学生端消息）
"""

from datetime import datetime
from typing import Optional, List
from app.models.database import (
    Student, Parent, StudentParentBinding, ParentNotification,
    get_db
)


class NotificationService:
    """通知服务类"""

    @staticmethod
    def send_to_parent(
        parent_id: str,
        student_id: str,
        notification_type: str,
        title: str,
        content: Optional[str] = None
    ) -> str:
        """
        发送通知到家长端
        返回通知ID
        """
        notification_id = f"notif_{parent_id}_{student_id}_{int(datetime.utcnow().timestamp())}"

        db_gen = get_db()
        db = next(db_gen)
        try:
            notification = ParentNotification(
                notification_id=notification_id,
                parent_id=parent_id,
                student_id=student_id,
                type=notification_type,
                title=title,
                content=content,
                is_read=False,
                sent_at=datetime.utcnow()
            )
            db.add(notification)
            db.commit()
        finally:
            db.close()

        return notification_id

    @staticmethod
    def send_practice_notification(student_id: str, practice_name: str) -> int:
        """
        发送练习通知给家长的绑定家长
        返回发送数量
        """
        db_gen = get_db()
        db = next(db_gen)
        sent_count = 0

        try:
            # 获取学生信息
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return 0

            # 获取绑定家长
            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student_id,
                StudentParentBinding.status == "active"
            ).all()

            for binding in bindings:
                notification = ParentNotification(
                    notification_id=f"prac_{student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                    parent_id=binding.parent_id,
                    student_id=student_id,
                    type="daily_report",
                    title=f"📝 {student.name} 今日练习已推送",
                    content=f"{practice_name}，请督促孩子完成",
                    is_read=False,
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                sent_count += 1

            db.commit()
        finally:
            db.close()

        return sent_count

    @staticmethod
    def send_weekly_report_notification(student_id: str) -> int:
        """
        发送周报通知给家长的绑定家长
        返回发送数量
        """
        db_gen = get_db()
        db = next(db_gen)
        sent_count = 0

        try:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return 0

            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student_id,
                StudentParentBinding.status == "active"
            ).all()

            for binding in bindings:
                notification = ParentNotification(
                    notification_id=f"week_{student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                    parent_id=binding.parent_id,
                    student_id=student_id,
                    type="weekly_report",
                    title=f"📊 {student.name} 本周学习周报已生成",
                    content="点击查看详细周报",
                    is_read=False,
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                sent_count += 1

            db.commit()
        finally:
            db.close()

        return sent_count

    @staticmethod
    def send_warning_notification(
        student_id: str,
        warning_type: str,
        message: str
    ) -> int:
        """
        发送预警通知给家长的绑定家长
        warning_type: 'no_login' / 'score_drop' / 'high_error_rate'
        """
        db_gen = get_db()
        db = next(db_gen)
        sent_count = 0

        try:
            student = db.query(Student).filter(Student.student_id == student_id).first()
            if not student:
                return 0

            bindings = db.query(StudentParentBinding).filter(
                StudentParentBinding.student_id == student_id,
                StudentParentBinding.status == "active"
            ).all()

            type_names = {
                'no_login': '📅 连续未学习提醒',
                'score_drop': '📉 成绩下滑预警',
                'high_error_rate': '⚠️ 错题率过高提醒'
            }

            title = type_names.get(warning_type, '⚠️ 学习提醒')

            for binding in bindings:
                notification = ParentNotification(
                    notification_id=f"warn_{warning_type}_{student_id}_{binding.parent_id}_{int(datetime.utcnow().timestamp())}",
                    parent_id=binding.parent_id,
                    student_id=student_id,
                    type="score_alert",
                    title=f"{title} - {student.name}",
                    content=message,
                    is_read=False,
                    sent_at=datetime.utcnow()
                )
                db.add(notification)
                sent_count += 1

            db.commit()
        finally:
            db.close()

        return sent_count


# 全局实例
notification_service = NotificationService()


def send_practice_notification(student_id: str, practice_name: str) -> int:
    """便捷函数"""
    return notification_service.send_practice_notification(student_id, practice_name)


def send_weekly_report_notification(student_id: str) -> int:
    """便捷函数"""
    return notification_service.send_weekly_report_notification(student_id)


def send_warning_notification(student_id: str, warning_type: str, message: str) -> int:
    """便捷函数"""
    return notification_service.send_warning_notification(student_id, warning_type, message)
