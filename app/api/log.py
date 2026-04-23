"""
操作日志API
GET /api/logs - 获取日志列表
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.database import get_db, OperationLog
from app.middleware.auth import PermissionChecker

router = APIRouter()


class LogResponse(BaseModel):
    success: bool
    logs: Optional[List[dict]] = None
    total: int = 0
    message: str = ""


@router.get("")
async def get_logs(
    request: Request,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    user_id: Optional[str] = None,
    days: Optional[int] = 7,  # 默认查询最近7天
    db: Session = Depends(get_db),
    current_user: dict = Depends(PermissionChecker("grade", "read"))  # 复用grade权限
):
    """
    获取操作日志列表
    只有admin可以查看
    """
    if current_user["role"] != "admin":
        return {"success": False, "message": "只有管理员可以查看日志", "logs": [], "total": 0}

    query = db.query(OperationLog)

    # 按动作筛选
    if action:
        query = query.filter(OperationLog.action == action)

    # 按目标类型筛选
    if target_type:
        query = query.filter(OperationLog.target_type == target_type)

    # 按用户筛选
    if user_id:
        query = query.filter(OperationLog.user_id == user_id)

    # 按时间筛选（最近N天）
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(OperationLog.created_at >= cutoff)

    # 按时间倒序
    logs = query.order_by(OperationLog.created_at.desc()).limit(500).all()

    return {
        "success": True,
        "total": len(logs),
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    }


@router.post("")
async def create_log(
    user_id: str,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    ip_address: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    记录操作日志（内部调用）
    """
    log = OperationLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()
    return {"success": True, "id": log.id}
