from sqlalchemy.orm import Session
from app.models import Phone
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("ncdc.status_checker")

def update_offline_phones(db: Session, timeout_minutes: int = 5):
    """Помечает телефоны как offline, если они не отправляли события более timeout_minutes"""
    cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    
    result = db.query(Phone).filter(
        Phone.status == "online",
        Phone.last_seen < cutoff_time
    ).update({"status": "offline"})
    
    db.commit()
    
    if result > 0:
        logger.info(f"✅ Обновлено {result} телефонов в статус offline")
    
    return result