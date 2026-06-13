"""
权限认证中间件
提供JWT认证和权限验证功能
纯Python实现，无需pyjwt依赖
"""
import json
import base64
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Callable
from fastapi import Request, HTTPException
import os

# JWT配置
SECRET_KEY = os.getenv("CHEMAI_JWT_SECRET", "chemai-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24  # 开发阶段延长至24小时
REFRESH_TOKEN_EXPIRE_DAYS = 7

# 权限配置
ROLE_PERMISSIONS = {
    'admin': {
        'school': ['create', 'read', 'update', 'delete'],
        'grade': ['create', 'read', 'update', 'delete'],
        'class': ['create', 'read', 'update', 'delete'],
        'teacher': ['create', 'read', 'update', 'delete'],
        'student': ['create', 'read', 'update', 'delete'],
        'analysis': ['read'],
    },
    '教务管理员': {
        'school': ['read'],
        'grade': ['create', 'read', 'update'],
        'class': ['create', 'read', 'update', 'delete'],
        'teacher': ['read', 'update'],
        'student': ['create', 'read', 'update', 'delete'],
        'analysis': ['read'],
    },
    '学科组长': {
        'school': ['read'],
        'grade': ['read'],
        'class': ['read'],
        'teacher': ['read'],
        'student': ['read'],
        'analysis': ['read'],
    },
    'teacher': {
        'school': ['read'],
        'grade': ['read'],
        'class': ['read'],
        'teacher': ['read'],
        'student': ['read'],
        'analysis': ['read'],
    },
    'student': {
        'self_data': ['read'],
        'assignment': ['read'],
        'grade': ['read'],
    }
}


def base64url_encode(data: bytes) -> str:
    """URL-safe base64编码"""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def base64url_decode(data: str) -> bytes:
    """URL-safe base64解码"""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += '=' * padding
    return base64.urlsafe_b64decode(data)


def create_jwt(payload: dict, secret: str, expires_in: int = None) -> str:
    """
    创建JWT token（简化实现）
    不依赖外部库
    """
    # 添加标准声明
    now = datetime.utcnow()
    payload['iat'] = int(now.timestamp())
    if expires_in:
        payload['exp'] = int((now + timedelta(hours=expires_in)).timestamp())

    # Header
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = base64url_encode(json.dumps(header, ensure_ascii=False).encode('utf-8'))
    payload_encoded = base64url_encode(json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    # Signature
    signature_input = f"{header_encoded}.{payload_encoded}"
    signature = hmac.new(
        secret.encode('utf-8'),
        signature_input.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_encoded = base64url_encode(signature)

    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"


def verify_jwt(token: str, secret: str, verify_exp: bool = True) -> Optional[dict]:
    """
    验证JWT token（简化实现）
    返回payload或None
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        header_encoded, payload_encoded, signature_encoded = parts

        # 验证签名
        signature_input = f"{header_encoded}.{payload_encoded}"
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            signature_input.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature_encoded = base64url_encode(expected_signature)

        if signature_encoded != expected_signature_encoded:
            return None

        # 解析payload
        payload = json.loads(base64url_decode(payload_encoded))

        # 验证过期时间
        if verify_exp and 'exp' in payload:
            exp = payload['exp']
            if datetime.utcnow().timestamp() > exp:
                return None  # token过期

        return payload

    except Exception:
        return None


def create_access_token(user_id: str, role: str, school_id: str = None, extra_data: dict = None) -> str:
    """创建访问令牌 (JWT)"""
    payload = {
        "user_id": user_id,
        "role": role,
        "school_id": school_id,
        "type": "access"
    }
    if extra_data:
        payload.update(extra_data)
    return create_jwt(payload, SECRET_KEY, expires_in=ACCESS_TOKEN_EXPIRE_HOURS)


def create_refresh_token(user_id: str) -> str:
    """创建刷新令牌"""
    payload = {
        "user_id": user_id,
        "type": "refresh"
    }
    return create_jwt(payload, SECRET_KEY, expires_in=REFRESH_TOKEN_EXPIRE_DAYS * 24)


def verify_token(token: str) -> Optional[dict]:
    """验证访问token"""
    payload = verify_jwt(token, SECRET_KEY, verify_exp=True)
    if payload and payload.get("type") == "access":
        return payload
    return None


def verify_refresh_token(token: str) -> Optional[dict]:
    """验证刷新token"""
    payload = verify_jwt(token, SECRET_KEY, verify_exp=True)
    if payload and payload.get("type") == "refresh":
        return payload
    return None


def can(role: str, resource: str, action: str) -> bool:
    """检查权限"""
    if not role or role not in ROLE_PERMISSIONS:
        return False
    permissions = ROLE_PERMISSIONS.get(role, {})
    resource_perms = permissions.get(resource, [])
    return action in resource_perms


def get_current_user(request: Request) -> dict:
    """
    从请求中获取当前用户信息
    用于FastAPI Depends
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="未携带token")

    token = auth_header.replace('Bearer ', '')
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="token无效或已过期")

    return {
        "user_id": payload.get('user_id'),
        "role": payload.get('role'),
        "school_id": payload.get('school_id')
    }


def require_auth(f: Callable):
    """
    登录验证装饰器
    用于FastAPI端点
    """
    @wraps(f)
    async def decorated(request: Request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="未携带token")

        token = auth_header.replace('Bearer ', '')
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="token无效或已过期")

        # 注入用户信息到request
        request.user_id = payload.get('user_id')
        request.user_role = payload.get('role')
        request.school_id = payload.get('school_id')

        return await f(request, *args, **kwargs)
    return decorated


def require_permission(resource: str, action: str):
    """
    权限验证装饰器工厂
    用于FastAPI端点

    用法:
        @router.get("/students")
        @require_permission("student", "read")
        async def get_students(request: Request):
            ...
    """
    def decorator(f: Callable):
        @wraps(f)
        async def decorated(request: Request, *args, **kwargs):
            # 先验证登录
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                raise HTTPException(status_code=401, detail="未携带token")

            token = auth_header.replace('Bearer ', '')
            payload = verify_token(token)
            if not payload:
                raise HTTPException(status_code=401, detail="token无效或已过期")

            # 注入用户信息
            request.user_id = payload.get('user_id')
            request.user_role = payload.get('role')
            request.school_id = payload.get('school_id')

            # 检查权限
            role = payload.get('role')
            if not can(role, resource, action):
                raise HTTPException(status_code=403, detail=f"无{resource}:{action}权限")

            return await f(request, *args, **kwargs)
        return decorated
    return decorator


class PermissionChecker:
    """
    权限检查器，用于FastAPI Depends

    用法:
        @router.get("/students")
        async def get_students(
            request: Request,
            current_user: dict = Depends(PermissionChecker("student", "read"))
        ):
            ...
    """

    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action

    def __call__(self, request: Request) -> dict:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            raise HTTPException(status_code=401, detail="未携带token")

        token = auth_header.replace('Bearer ', '')
        payload = verify_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="token无效或已过期")

        role = payload.get('role')
        if not can(role, self.resource, self.action):
            raise HTTPException(status_code=403, detail=f"无{self.resource}:{self.action}权限")

        return {
            "user_id": payload.get('user_id'),
            "role": role,
            "school_id": payload.get('school_id')
        }


def get_teacher_classes(db, teacher_id: str, role: str) -> list:
    """
    获取教师任教的班级列表
    根据角色不同返回不同范围的班级
    """
    from app.models.database import Class, TeacherClassSubject, Teacher

    if role == 'admin':
        # 管理员看所有班级
        return db.query(Class).all()

    if role in ['教务管理员', '学科组长']:
        # 查找教师所在的学校
        teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
        if not teacher or not teacher.school_id:
            return []
        # 返回同学校的所有班级
        return db.query(Class).filter(Class.grade_id.in_(
            db.query(TeacherClassSubject.class_id).filter(
                TeacherClassSubject.teacher_id == teacher_id
            ).subquery()
        )).all()

    # 普通教师只看自己任教的班级
    tcs_records = db.query(TeacherClassSubject).filter(
        TeacherClassSubject.teacher_id == teacher_id
    ).all()
    class_ids = [r.class_id for r in tcs_records]
    if not class_ids:
        return []
    return db.query(Class).filter(Class.class_id.in_(class_ids)).all()


def get_class_students(db, class_id: str, teacher_id: str = None, role: str = None) -> list:
    """
    获取班级的学生列表
    会根据教师权限自动过滤
    """
    from app.models.database import Student, Class

    # 管理员和教务管理员可以看任何班级
    if role in ['admin', '教务管理员']:
        return db.query(Student).filter(Student.class_id == class_id).all()

    # 其他教师只能看自己任教的班级
    if teacher_id:
        from app.models.database import TeacherClassSubject
        tcs = db.query(TeacherClassSubject).filter(
            TeacherClassSubject.teacher_id == teacher_id,
            TeacherClassSubject.class_id == class_id
        ).first()
        if not tcs:
            return []  # 无权访问该班级

    return db.query(Student).filter(Student.class_id == class_id).all()
