from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/")
async def audit_log(
    request: Request,
    db: Session = Depends(get_db),
    days: Optional[int] = Query(default=7, description="Показать логи за последние N дней"),
    action: Optional[str] = Query(default=None, description="Фильтр по типу действия"),
    page: int = Query(default=1, description="Номер страницы"),
    per_page: int = Query(default=50, description="Записей на странице")
):
    """Просмотр журнала аудита с фильтрацией и пагинацией"""
    
    # Базовый запрос
    query = db.query(AuditLog)
    
    # Фильтр по дате
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.timestamp >= cutoff_date)
    
    # Фильтр по типу действия
    if action:
        query = query.filter(AuditLog.action == action)
    
    # Сортировка по дате (новые сверху)
    query = query.order_by(desc(AuditLog.timestamp))
    
    # Подсчет общего количества
    total = query.count()
    
    # Пагинация
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()
    
    # Статистика по действиям (ИСПРАВЛЕНО: используем func вместо db.func)
    action_stats = db.query(
        AuditLog.action,
        func.count(AuditLog.id).label('count')
    ).group_by(AuditLog.action).all()
    
    # Доступные типы действий
    available_actions = [stat.action for stat in action_stats]
    
    # Общее количество страниц
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    
    return request.app.state.templates.TemplateResponse("audit/log.html", {
        "request": request,
        "logs": logs,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "days": days,
        "action": action,
        "available_actions": available_actions,
        "action_stats": action_stats
    })

@router.get("/clear")
async def clear_audit_log(
    request: Request,
    db: Session = Depends(get_db),
    days: Optional[int] = Query(default=30, description="Удалить логи старше N дней")
):
    """Очистка старых логов аудита"""
    if days:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
        db.commit()
        return {"status": "success", "message": f"Удалено {deleted} записей старше {days} дней"}
    
    return {"status": "error", "message": "Не указан параметр days"}