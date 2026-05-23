"""
家长端 API
支持家长注册、登录、子女绑定、通知接收等功能
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import hashlib
import uuid

from sqlalchemy.orm import Session
from app.models.database import (
    Parent, StudentParentBinding, ParentNotification, Account, Student, Class,
    get_db
)

router = APIRouter()


# ==================== 辅助函数 ====================

def hash_password(password: str) -> str:
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


# ==================== Request/Response Models ====================

class ParentRegisterRequest(BaseModel):
    """家长注册请求"""
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    password: str


class ParentLoginRequest(BaseModel):
    """家长登录请求"""
    username: str
    password: str


class BindStudentRequest(BaseModel):
    """绑定学生请求"""
    student_id: str
    bind_code: str
    relation: str = "家长"  # 父亲/母亲/其他


class SendBindCodeRequest(BaseModel):
    """发送绑定码请求"""
    student_id: str


class WeeklyReportResponse(BaseModel):
    """周报响应"""
    student_id: str
    student_name: str
    week_start: str
    week_end: str
    practice_count: int
    practice_completed: int
    accuracy_rate: float
    weak_knowledge_points: List[str]
    barrier_type: str
    streak_days: int


class ChildInfo(BaseModel):
    """子女信息"""
    student_id: str
    student_name: str
    class_name: str
    grade: str
    relation: str
    binding_id: str


class NotificationInfo(BaseModel):
    """通知信息"""
    notification_id: str
    student_id: str
    student_name: str
    type: str
    title: str
    content: Optional[str]
    is_read: bool
    created_at: str


# ==================== API 端点 ====================

@router.post("/register")
async def register_parent(
    data: ParentRegisterRequest,
    db: Session = Depends(get_db)
):
    """注册家长账号"""
    # 检查用户名是否已存在
    # 修复: Python 'or' 优先级导致永远匹配，改用 SQLAlchemy '|' 操作符
    from sqlalchemy import or_
    existing = db.query(Account).filter(
        or_(Account.username == data.phone, Account.username == data.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 创建家长
    parent_id = generate_id("parent_")
    parent = Parent(
        parent_id=parent_id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        password_hash=hash_password(data.password)
    )
    db.add(parent)

    # 创建账户（使用手机号或邮箱作为用户名）
    username = data.phone or data.email
    account = Account(
        account_id=generate_id("acct_"),
        role="parent",
        username=username,
        password_hash=hash_password(data.password),
        parent_id=parent_id
    )
    db.add(account)
    db.commit()

    return {
        "success": True,
        "message": "注册成功",
        "parent_id": parent_id
    }


@router.post("/login")
async def login_parent(
    data: ParentLoginRequest,
    db: Session = Depends(get_db)
):
    """家长登录"""
    account = db.query(Account).filter(
        Account.username == data.username,
        Account.role == "parent"
    ).first()

    if not account:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if account.password_hash != hash_password(data.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if account.status != "active":
        raise HTTPException(status_code=401, detail="账号已被禁用")

    # 获取家长信息
    parent = db.query(Parent).filter(Parent.parent_id == account.parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="家长信息不存在")

    return {
        "success": True,
        "message": "登录成功",
        "parent_id": parent.parent_id,
        "name": parent.name,
        "role": "parent"
    }


@router.get("/children")
async def get_children(
    parent_id: str,
    db: Session = Depends(get_db)
):
    """获取已绑定子女列表"""
    bindings = db.query(StudentParentBinding).filter(
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).all()

    children = []
    for binding in bindings:
        student = db.query(Student).filter(Student.student_id == binding.student_id).first()
        if student:
            class_obj = db.query(Class).filter(Class.class_id == student.class_id).first()
            children.append(ChildInfo(
                student_id=student.student_id,
                student_name=student.name,
                class_name=class_obj.name if class_obj else "未知班级",
                grade=class_obj.grade if class_obj else "未知年级",
                relation=binding.relation,
                binding_id=binding.binding_id
            ))

    return {
        "success": True,
        "children": [c.model_dump() for c in children]
    }


@router.post("/bind")
async def bind_student(
    data: BindStudentRequest,
    db: Session = Depends(get_db)
):
    """绑定学生（通过绑定码）"""
    # 查找学生
    student = db.query(Student).filter(Student.student_id == data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 验证绑定码
    if student.bind_code != data.bind_code:
        raise HTTPException(status_code=400, detail="绑定码错误")

    # 检查是否已经绑定
    existing = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == data.student_id,
        StudentParentBinding.parent_id == data.parent_id,
        StudentParentBinding.status == "active"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已经绑定过该学生")

    # 创建绑定关系
    binding = StudentParentBinding(
        binding_id=generate_id("bind_"),
        student_id=data.student_id,
        parent_id=data.parent_id,
        relation=data.relation,
        bind_code=data.bind_code,
        status="active"
    )
    db.add(binding)
    db.commit()

    return {
        "success": True,
        "message": "绑定成功",
        "binding_id": binding.binding_id,
        "student_name": student.name
    }


@router.delete("/bind/{binding_id}")
async def unbind_student(
    binding_id: str,
    parent_id: str,
    db: Session = Depends(get_db)
):
    """解除绑定"""
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.binding_id == binding_id,
        StudentParentBinding.parent_id == parent_id
    ).first()

    if not binding:
        raise HTTPException(status_code=404, detail="绑定关系不存在")

    binding.status = "inactive"
    db.commit()

    return {
        "success": True,
        "message": "解除绑定成功"
    }


@router.get("/notifications")
async def get_notifications(
    parent_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """获取通知列表"""
    notifications = db.query(ParentNotification).filter(
        ParentNotification.parent_id == parent_id
    ).order_by(ParentNotification.created_at.desc()).limit(limit).offset(offset).all()

    result = []
    for n in notifications:
        student = db.query(Student).filter(Student.student_id == n.student_id).first()
        result.append(NotificationInfo(
            notification_id=n.notification_id,
            student_id=n.student_id,
            student_name=student.name if student else "未知",
            type=n.type,
            title=n.title,
            content=n.content,
            is_read=n.is_read,
            created_at=n.created_at.isoformat() if n.created_at else ""
        ))

    return {
        "success": True,
        "notifications": [r.model_dump() for r in result]
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    parent_id: str,
    db: Session = Depends(get_db)
):
    """标记通知已读"""
    notification = db.query(ParentNotification).filter(
        ParentNotification.notification_id == notification_id,
        ParentNotification.parent_id == parent_id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    notification.is_read = True
    db.commit()

    return {
        "success": True,
        "message": "已标记为已读"
    }


@router.get("/child/{student_id}/report")
async def get_child_report(
    student_id: str,
    parent_id: str,
    db: Session = Depends(get_db)
):
    """获取子女报告摘要"""
    # 验证绑定关系
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).first()

    if not binding:
        raise HTTPException(status_code=403, detail="未绑定该学生")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    class_obj = db.query(Class).filter(Class.class_id == student.class_id).first()

    return {
        "success": True,
        "report": {
            "student_id": student_id,
            "student_name": student.name,
            "class_name": class_obj.name if class_obj else "未知班级",
            "grade": class_obj.grade if class_obj else "未知年级",
            "exercises_completed": student.exercises_completed,
            "barrier_type": student.barrier_type,
            "last_exercise_at": student.last_exercise_at.isoformat() if student.last_exercise_at else None
        }
    }


@router.get("/child/{student_id}/weekly")
async def get_child_weekly(
    student_id: str,
    parent_id: str,
    db: Session = Depends(get_db)
):
    """获取子女周报"""
    # 验证绑定关系
    binding = db.query(StudentParentBinding).filter(
        StudentParentBinding.student_id == student_id,
        StudentParentBinding.parent_id == parent_id,
        StudentParentBinding.status == "active"
    ).first()

    if not binding:
        raise HTTPException(status_code=403, detail="未绑定该学生")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 获取本周通知作为周报内容
    from datetime import timedelta
    week_start = datetime.utcnow() - timedelta(days=7)

    weekly_notifications = db.query(ParentNotification).filter(
        ParentNotification.student_id == student_id,
        ParentNotification.created_at >= week_start
    ).all()

    # 计算本周练习情况
    practice_count = len([n for n in weekly_notifications if n.type == "daily_report"])
    practice_completed = len([n for n in weekly_notifications if n.type == "daily_report" and n.is_read])

    return {
        "success": True,
        "weekly": WeeklyReportResponse(
            student_id=student_id,
            student_name=student.name,
            week_start=week_start.strftime("%Y-%m-%d"),
            week_end=datetime.utcnow().strftime("%Y-%m-%d"),
            practice_count=practice_count,
            practice_completed=practice_completed,
            accuracy_rate=0.85,  # TODO: 实际计算
            weak_knowledge_points=["盐类水解", "电离平衡"],  # TODO: 实际获取
            barrier_type=student.barrier_type.get("concept", 0.33) if student.barrier_type else "未知",
            streak_days=student.exercises_completed % 30  # TODO: 实际计算连续天数
        ).model_dump()
    }


@router.post("/send-bind-code/{student_id}")
async def send_bind_code(
    student_id: str,
    db: Session = Depends(get_db)
):
    """生成并发送绑定码给学生（由学生在自己的客户端调用）"""
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 生成新的绑定码（6位数字）
    import random
    bind_code = str(random.randint(100000, 999999))
    student.bind_code = bind_code
    db.commit()

    return {
        "success": True,
        "bind_code": bind_code,
        "message": "绑定码已生成，请在家长端输入"
    }


@router.post("/notify")
async def create_notification(
    parent_id: str,
    student_id: str,
    notification_type: str,
    title: str,
    content: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """创建通知（由教师端调用）"""
    notification = ParentNotification(
        notification_id=generate_id("notif_"),
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

    return {
        "success": True,
        "notification_id": notification.notification_id
    }
