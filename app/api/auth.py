"""
认证相关API
POST /api/auth/login - 登录
POST /api/auth/logout - 登出
POST /api/auth/refresh - 刷新Token
POST /api/auth/apply - 教师入驻申请
GET /api/auth/me - 获取当前用户
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import hashlib
from sqlalchemy.orm import Session

from app.models.database import get_db, Teacher, Student, Account, TeacherApplication, Parent, StudentParentBinding
from app.middleware.auth import (
    create_access_token, create_refresh_token, verify_token, verify_refresh_token,
    get_current_user as mw_get_current_user
)

router = APIRouter()


def hash_password(password: str) -> str:
    """哈希密码（SHA256）"""
    return hashlib.sha256(password.encode()).hexdigest()


class LoginRequest(BaseModel):
    username: str
    password: str


class ApplyRequest(BaseModel):
    name: str
    phone: str
    school: str
    subject: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    success: bool
    message: str = ""
    user: Optional[dict] = None
    token: Optional[str] = None
    refresh_token: Optional[str] = None


def get_user_info(account: Account, db: Session) -> dict:
    """从账户获取用户信息"""
    user_info = {
        "id": account.account_id,
        "role": account.role,
        "username": account.username
    }

    if account.role in ("teacher", "学科组长", "教务管理员") and account.teacher_id:
        teacher = db.query(Teacher).filter(Teacher.teacher_id == account.teacher_id).first()
        if teacher:
            user_info["name"] = teacher.name
            user_info["id"] = teacher.teacher_id
            user_info["teacher_id"] = teacher.teacher_id
            user_info["status"] = teacher.status
            user_info["school_id"] = teacher.school_id

    elif account.role == "student" and account.student_id:
        student = db.query(Student).filter(Student.student_id == account.student_id).first()
        if student:
            user_info["name"] = student.name
            user_info["id"] = student.student_id
            user_info["student_id"] = student.student_id
            user_info["class_id"] = student.class_id
            user_info["status"] = student.status

    elif account.role == "admin":
        user_info["name"] = "管理员"
        user_info["status"] = "approved"
        # 尝试获取admin的teacher_id以获取school_id
        if account.teacher_id:
            admin_teacher = db.query(Teacher).filter(Teacher.teacher_id == account.teacher_id).first()
            if admin_teacher:
                user_info["school_id"] = admin_teacher.school_id

    elif account.role == "parent" and account.parent_id:
        parent = db.query(Parent).filter(Parent.parent_id == account.parent_id).first()
        if parent:
            user_info["name"] = parent.name
            user_info["id"] = parent.parent_id
            user_info["parent_id"] = parent.parent_id
            user_info["status"] = parent.status
            # 获取绑定的学生信息
            binding = db.query(StudentParentBinding).filter(
                StudentParentBinding.parent_id == parent.parent_id,
                StudentParentBinding.status == "active"
            ).first()
            if binding:
                student = db.query(Student).filter(Student.student_id == binding.student_id).first()
                if student:
                    user_info["student_id"] = student.student_id
                    user_info["student_name"] = student.name
                    user_info["class_id"] = student.class_id

    return user_info


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    用户登录
    返回JWT token
    """
    # 查找账户
    account = db.query(Account).filter(Account.username == request.username).first()
    if not account:
        return AuthResponse(success=False, message="用户名或密码错误")

    # 验证密码
    if account.password_hash != hash_password(request.password):
        return AuthResponse(success=False, message="用户名或密码错误")

    # 检查账户状态
    if account.status != "active":
        return AuthResponse(success=False, message="账户已被禁用")

    # 获取用户信息
    user_info = get_user_info(account, db)

    # 生成JWT token
    token = create_access_token(
        user_id=user_info["id"],
        role=user_info["role"],
        school_id=user_info.get("school_id")
    )
    refresh_token = create_refresh_token(user_id=user_info["id"])

    return AuthResponse(
        success=True,
        message="登录成功",
        user=user_info,
        token=token,
        refresh_token=refresh_token
    )


@router.post("/refresh")
async def refresh_token(request: RefreshRequest, db: Session = Depends(get_db)):
    """
    刷新Access Token
    """
    payload = verify_refresh_token(request.refresh_token)
    if not payload:
        return {"success": False, "message": "refresh token无效"}

    user_id = payload.get("user_id")

    # 获取账户信息
    account = db.query(Account).filter(Account.account_id == user_id).first()
    if not account:
        return {"success": False, "message": "用户不存在"}

    if account.status != "active":
        return {"success": False, "message": "账户已被禁用"}

    user_info = get_user_info(account, db)

    # 生成新的access token
    new_token = create_access_token(
        user_id=user_info["id"],
        role=user_info["role"],
        school_id=user_info.get("school_id")
    )

    return {
        "success": True,
        "access_token": new_token,
        "user": user_info
    }


@router.post("/logout")
async def logout(request: Request, authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    用户登出
    """
    # JWT不需要在服务端存储token，客户端删除token即可
    return {"success": True, "message": "已退出登录"}


@router.get("/me")
async def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    获取当前用户信息
    需要携带token（Header: Authorization: Bearer <token>）
    """
    if not authorization:
        return {"success": False, "message": "未登录", "user": None}

    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if not payload:
        return {"success": False, "message": "token无效", "user": None}

    user_id = payload.get("user_id")

    # 查找账户
    account = db.query(Account).filter(Account.account_id == user_id).first()
    if not account:
        return {"success": False, "message": "用户不存在", "user": None}

    user_info = get_user_info(account, db)
    return {"success": True, "user": user_info}


@router.post("/apply")
async def teacher_apply(request: ApplyRequest, db: Session = Depends(get_db)):
    """
    教师入驻申请
    """
    # 检查手机号是否已申请
    existing = db.query(TeacherApplication).filter(
        TeacherApplication.phone == request.phone
    ).first()
    if existing:
        if existing.status == "pending":
            return {"success": False, "message": "该手机号已提交申请，请等待审核"}
        elif existing.status == "approved":
            return {"success": False, "message": "该手机号已审核通过，请直接登录"}

    # 创建申请
    app_id = f"app_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    application = TeacherApplication(
        id=app_id,
        name=request.name,
        phone=request.phone,
        school=request.school,
        subject=request.subject,
        status="pending"
    )
    db.add(application)
    db.commit()

    return {
        "success": True,
        "message": "申请已提交，请等待管理员审核",
        "application_id": app_id
    }


@router.get("/apply/{app_id}")
async def get_application(app_id: str, db: Session = Depends(get_db)):
    """获取申请状态"""
    application = db.query(TeacherApplication).filter(
        TeacherApplication.id == app_id
    ).first()
    if not application:
        return {"success": False, "message": "申请不存在"}

    return {
        "success": True,
        "application": {
            "id": application.id,
            "name": application.name,
            "phone": application.phone,
            "school": application.school,
            "subject": application.subject,
            "status": application.status,
            "created_at": application.created_at.isoformat() if application.created_at else None
        }
    }
