"""
P0-1: 通知服务 API
提供三端消息推送、通知管理功能
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import get_db, Student, Parent, Teacher
from app.services.notification_service import notification_service

router = APIRouter()


class NotificationSendRequest(BaseModel):
    """发送通知请求"""
    type: str  # daily_report/weekly_report/score_alert/warning/reminder
    title: str
    content: str
    target_type: str  # student/parent/teacher
    target_ids: Optional[List[str]] = None  # 指定ID列表，None表示全部
    priority: str = "normal"  # normal/high/immediate
    channel: str = "in_app"  # in_app/sms/email/telegram


class NotificationResponse(BaseModel):
    """通知响应"""
    notification_id: str
    success: bool
    message: str
    sent_count: int = 0
    failed_count: int = 0


class NotificationRecord(BaseModel):
    """通知记录"""
    notification_id: str
    type: str
    title: str
    content: str
    target_type: str
    target_count: int
    sent_count: int
    failed_count: int
    status: str
    created_at: str
    sent_at: Optional[str] = None


@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationSendRequest,
    db: Session = Depends(get_db)
):
    """
    发送通知给指定用户群体
    支持按类型（学生/家长/教师）和ID列表精确发送
    """
    try:
        result = notification_service.send_notification(
            notification_type=request.type,
            title=request.title,
            content=request.content,
            target_type=request.target_type,
            target_ids=request.target_ids,
            priority=request.priority,
            channel=request.channel
        )

        return NotificationResponse(
            notification_id=result.get("notification_id", ""),
            success=result.get("success", False),
            message=result.get("message", ""),
            sent_count=result.get("sent_count", 0),
            failed_count=result.get("failed_count", 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-to-student/{student_id}")
async def send_to_student(
    student_id: str,
    notification_type: str,
    title: str,
    content: str,
    db: Session = Depends(get_db)
):
    """
    发送通知给单个学生
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    result = notification_service.send_notification(
        notification_type=notification_type,
        title=title,
        content=content,
        target_type="student",
        target_ids=[student_id]
    )

    return result


@router.post("/send-to-parent/{student_id}")
async def send_to_parent(
    student_id: str,
    notification_type: str,
    title: str,
    content: str,
    db: Session = Depends(get_db)
):
    """
    发送通知给学生家长
    自动查找该学生绑定的家长
    """
    # 查找学生绑定的家长
    from app.models.database import StudentParentBinding

    bindings = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.status == "active"
    ).all()

    if not bindings:
        return {
            "success": False,
            "message": "该学生未绑定家长",
            "sent_count": 0
        }

    parent_ids = [b.parent_id for b in bindings]

    result = notification_service.send_notification(
        notification_type=notification_type,
        title=title,
        content=content,
        target_type="parent",
        target_ids=parent_ids
    )

    return result


@router.post("/send-to-class/{class_id}")
async def send_to_class(
    class_id: str,
    notification_type: str,
    title: str,
    content: str,
    target: str = "students",  # students/parents/teachers
    db: Session = Depends(get_db)
):
    """
    发送通知给整个班级
    target: students(学生) / parents(家长) / teachers(教师)
    """
    if target == "students":
        students = db.query(Student).filter(Student.class_id == class_id).all()
        student_ids = [s.student_id for s in students]

        result = notification_service.send_notification(
            notification_type=notification_type,
            title=title,
            content=content,
            target_type="student",
            target_ids=student_ids
        )
    elif target == "parents":
        # 查找班级所有学生的家长
        from app.models.database import StudentParentBinding

        bindings = db.query(StudentParentBinding).filter(
            StudentParentBinding.student_id.in_(
                db.query(Student.student_id).filter(Student.class_id == class_id)
            ),
            StudentParentBinding.status == "active"
        ).all()

        parent_ids = list(set([b.parent_id for b in bindings]))

        result = notification_service.send_notification(
            notification_type=notification_type,
            title=title,
            content=content,
            target_type="parent",
            target_ids=parent_ids
        )
    elif target == "teachers":
        from app.models.database import TeacherClassSubject

        tcs = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.class_id == class_id
        ).all()

        teacher_ids = list(set([tc.teacher_id for tc in tcs]))

        result = notification_service.send_notification(
            notification_type=notification_type,
            title=title,
            content=content,
            target_type="teacher",
            target_ids=teacher_ids
        )
    else:
        return {"success": False, "message": f"不支持的target类型: {target}"}

    return result


@router.get("/history")
async def get_notification_history(
    target_type: Optional[str] = None,
    notification_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    获取通知发送历史
    """
    # TODO: 从数据库查询通知历史
    # 目前返回空列表占位
    return {
        "success": True,
        "total": 0,
        "offset": offset,
        "limit": limit,
        "notifications": []
    }


@router.get("/student/{student_id}/notifications")
async def get_student_notifications(
    student_id: str,
    unread_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取学生的通知列表
    """
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # TODO: 从数据库查询学生通知
    return {
        "success": True,
        "student_id": student_id,
        "total": 0,
        "unread_count": 0,
        "notifications": []
    }


@router.get("/parent/{parent_id}/notifications")
async def get_parent_notifications(
    parent_id: str,
    unread_only: bool = False,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    获取家长的通知列表
    """
    parent = db.query(Parent).filter(Parent.parent_id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="家长不存在")

    # TODO: 从数据库查询家长通知
    return {
        "success": True,
        "parent_id": parent_id,
        "total": 0,
        "unread_count": 0,
        "notifications": []
    }


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user_id: str,
    user_type: str,  # student/parent/teacher
    db: Session = Depends(get_db)
):
    """
    标记通知为已读
    """
    # TODO: 更新数据库中的已读状态
    return {
        "success": True,
        "notification_id": notification_id,
        "message": "已标记为已读"
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """
    删除通知
    """
    # TODO: 从数据库删除通知
    return {
        "success": True,
        "notification_id": notification_id,
        "message": "通知已删除"
    }


@router.get("/channels")
async def get_available_channels():
    """
    获取可用的通知渠道
    """
    return {
        "success": True,
        "channels": [
            {"id": "in_app", "name": "端内通知", "enabled": True},
            {"id": "telegram", "name": "Telegram", "enabled": True},
            {"id": "email", "name": "邮件", "enabled": False},
            {"id": "sms", "name": "短信", "enabled": False}
        ]
    }


@router.post("/test-telegram")
async def test_telegram_channel(
    chat_id: str,
    message: str = "ChemAI测试消息"
):
    """
    测试Telegram渠道
    """
    result = notification_service.send_telegram(chat_id, message)
    return result


@router.post("/subscribe")
async def subscribe_notification_channel(
    user_id: str,
    user_type: str,
    channel: str,
    channel_id: str,  # telegram_chat_id / email / phone
    db: Session = Depends(get_db)
):
    """
    订阅通知渠道（如绑定Telegram机器人）
    """
    # TODO: 保存订阅信息到数据库
    return {
        "success": True,
        "message": f"已成功订阅{channel}通知",
        "user_id": user_id,
        "channel": channel,
        "channel_id": channel_id
    }


@router.delete("/unsubscribe")
async def unsubscribe_notification_channel(
    user_id: str,
    user_type: str,
    channel: str,
    db: Session = Depends(get_db)
):
    """
    取消订阅通知渠道
    """
    # TODO: 从数据库删除订阅信息
    return {
        "success": True,
        "message": f"已取消{channel}通知订阅"
    }
