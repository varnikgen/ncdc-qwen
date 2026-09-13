"""Запись строк в audit_logs.

user берётся из request.state.admin_user, который выставляет
basic_auth_middleware после успешного логина.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import AuditLog


def log_action(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: int | None,
    user: str = "system",
    details: str = "",
):
    log_entry = AuditLog(
        timestamp=datetime.utcnow(),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user=user,
        details=details,
    )
    db.add(log_entry)
    db.commit()
    return log_entry


def admin_user(request) -> str:
    """Имя админа из middleware; 'admin' — запасной вариант для фоновых вызовов."""
    return getattr(getattr(request, "state", None), "admin_user", None) or "admin"
