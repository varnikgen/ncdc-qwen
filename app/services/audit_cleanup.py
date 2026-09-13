"""Фоновый цикл (раз в минуту): чистка аудита и перевод молчащих трубок в offline.

Сессия своя, не из Depends: задача живёт всё время процесса.
При ошибке — rollback + close в finally, иначе SQLite остаётся залоченной.
"""
import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models import AuditLog, Phone

logger = logging.getLogger("ncdc.maintenance")


async def check_phone_availability(phone_ip: str, timeout: int = 3) -> bool:
    """HTTPS до веб-UI. 401/403 тоже «жив» — интерфейс отвечает, просто закрыт паролем."""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=settings.AUTOP_VERIFY_SSL) as client:
            response = await client.get(f"https://{phone_ip}/")
            return response.status_code in (200, 401, 403)
    except Exception:
        return False


async def background_tasks():
    logger.info(
        "Background tasks started (audit %s days, offline timeout %s min)",
        settings.AUDIT_RETENTION_DAYS,
        settings.OFFLINE_TIMEOUT_MINUTES,
    )

    while True:
        await asyncio.sleep(60)
        db = SessionLocal()
        try:
            cutoff_audit = datetime.utcnow() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
            deleted_logs = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_audit).delete()
            if deleted_logs:
                logger.info("Purged %s audit rows", deleted_logs)

            cutoff_phone = datetime.utcnow() - timedelta(minutes=settings.OFFLINE_TIMEOUT_MINUTES)
            offline_candidates = (
                db.query(Phone)
                .filter(
                    Phone.status.in_(["online", "dnd"]),
                    Phone.last_seen < cutoff_phone,
                    Phone.ip_address.isnot(None),
                )
                .all()
            )

            dirty = bool(deleted_logs) or bool(offline_candidates)
            for phone in offline_candidates:
                # Action URL мог не дойти, но веб-UI ещё жив — не помечаем offline
                is_available = await check_phone_availability(phone.ip_address)
                if is_available:
                    phone.last_seen = datetime.utcnow()
                    logger.info("Phone %s still reachable, last_seen refreshed", phone.mac)
                else:
                    phone.status = "offline"
                    logger.warning("Phone %s marked offline", phone.mac)

            if dirty:
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Background task failed")
        finally:
            db.close()
