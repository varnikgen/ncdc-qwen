"""JSON-статистика /dashboard/stats.

HTML главной рендерится в app.main:dashboard. Этот эндпоинт — для опроса
цифр без перезагрузки страницы.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Phone, Account, PhoneModel, AuditLog

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    status_counts = (
        db.query(Phone.status, func.count(Phone.id).label("count")).group_by(Phone.status).all()
    )
    status_dict = {"online": 0, "offline": 0, "unregistered": 0, "dnd": 0}
    for row in status_counts:
        if row.status in status_dict:
            status_dict[row.status] = row.count

    recent_logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10).all()
    return {
        "phones_count": db.query(Phone).count(),
        "accounts_count": db.query(Account).count(),
        "models_count": db.query(PhoneModel).count(),
        "status": status_dict,
        "recent_logs": [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in recent_logs
        ],
    }
