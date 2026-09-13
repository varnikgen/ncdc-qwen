"""Журнал аудита: просмотр с пагинацией и ручная очистка старше N дней.

Автоочистка по AUDIT_RETENTION_DAYS живёт в services.audit_cleanup.
"""
from fastapi import APIRouter, Depends, Request, Query, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import AuditLog
from app.services.audit import log_action, admin_user

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/")
async def audit_log(
    request: Request,
    db: Session = Depends(get_db),
    days: Optional[int] = Query(default=7),
    action: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
):
    query = db.query(AuditLog)
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.timestamp >= cutoff_date)
    if action:
        query = query.filter(AuditLog.action == action)
    query = query.order_by(desc(AuditLog.timestamp))
    total = query.count()
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()

    action_stats = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.action)
        .all()
    )
    available_actions = [stat.action for stat in action_stats]
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    return request.app.state.templates.TemplateResponse(
        "audit/log.html",
        {
            "request": request,
            "logs": logs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "days": days,
            "action": action,
            "available_actions": available_actions,
            "action_stats": action_stats,
        },
    )


@router.post("/clear")
async def clear_audit_log(
    request: Request,
    db: Session = Depends(get_db),
    days: int = Form(default=30),
):
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
    db.commit()
    log_action(
        db,
        "CLEAR_AUDIT",
        "AuditLog",
        None,
        admin_user(request),
        f"Deleted {deleted} records older than {days} days",
    )
    return {"status": "success", "message": f"Удалено {deleted} записей старше {days} дней"}
