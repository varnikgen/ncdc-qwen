from datetime import datetime
from sqlalchemy.orm import Session
from app.models import AuditLog

def log_action(db: Session, action: str, entity_type: str, entity_id: int, user: str = "system", details: str = ""):
    """Записывает действие в журнал аудита."""
    log_entry = AuditLog(
        timestamp=datetime.utcnow(),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user=user,
        details=details
    )
    db.add(log_entry)
    db.commit()
    return log_entry