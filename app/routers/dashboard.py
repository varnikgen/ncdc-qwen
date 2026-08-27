from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Phone, Account, PhoneModel, AuditLog

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    # Подсчёт телефонов по статусам
    status_counts = db.query(
        Phone.status,
        func.count(Phone.id).label('count')
    ).group_by(Phone.status).all()
    
    status_dict = {
        'registered': 0,
        'offline': 0,
        'unregistered': 0,
        'dnd': 0
    }
    
    for row in status_counts:
        if row.status == 'online':
            status_dict['registered'] = row.count
        elif row.status == 'offline':
            status_dict['offline'] = row.count
        elif row.status == 'unregistered':
            status_dict['unregistered'] = row.count
        elif row.status == 'dnd':
            status_dict['dnd'] = row.count
    
    # Общие счётчики
    phones_count = db.query(Phone).count()
    accounts_count = db.query(Account).count()
    models_count = db.query(PhoneModel).count()
    
    # Последние логи
    recent_logs = db.query(AuditLog).order_by(
        AuditLog.timestamp.desc()
    ).limit(10).all()
    
    return {
        "phones_count": phones_count,
        "accounts_count": accounts_count,
        "models_count": models_count,
        "status": status_dict,
        "recent_logs": [
            {
                "id": log.id,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "timestamp": log.timestamp
            }
            for log in recent_logs
        ]
    }