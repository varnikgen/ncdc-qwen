import asyncio
import logging
import os
from datetime import datetime, timedelta

import httpx
from app.database import SessionLocal
from app.models import AuditLog, Phone

logger = logging.getLogger("uvicorn.error")

RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))
OFFLINE_TIMEOUT_MINUTES = int(os.getenv("OFFLINE_TIMEOUT_MINUTES", "5"))  # Увеличили с 5 до 15 минут

async def check_phone_availability(phone_ip: str, timeout: int = 3) -> bool:
    """Проверяет доступность телефона через HTTP"""
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            response = await client.get(f"https://{phone_ip}/")
            return response.status_code in [200, 401, 403]  # Телефон отвечает (401/403 = есть веб-интерфейс)
    except Exception:
        return False

async def background_tasks():
    print(f"🕒 [BACKGROUND] Запущены фоновые задачи (Аудит: {RETENTION_DAYS} дн., Статусы: {OFFLINE_TIMEOUT_MINUTES} мин.)")
    logger.info("Запущены фоновые задачи обслуживания системы")
    
    while True:
        await asyncio.sleep(60)  # Проверка каждую минуту
        
        try:
            db = SessionLocal()
            
            # --- ЗАДАЧА 1: Очистка старых логов ---
            cutoff_audit = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
            deleted_logs = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_audit).delete()
            if deleted_logs > 0:
                logger.info(f"🧹 Удалено {deleted_logs} старых записей аудита")
            
            # --- ЗАДАЧА 2: Перевод телефонов в offline с проверкой ---
            cutoff_phone = datetime.utcnow() - timedelta(minutes=OFFLINE_TIMEOUT_MINUTES)
            offline_candidates = db.query(Phone).filter(
                Phone.status.in_(["online", "dnd"]),
                Phone.last_seen < cutoff_phone,
                Phone.ip_address.isnot(None)
            ).all()
            
            for phone in offline_candidates:
                # Проверяем доступность телефона
                is_available = await check_phone_availability(phone.ip_address)
                
                if is_available:
                    # Телефон доступен, но не отправляет Action URL
                    # Обновляем last_seen, чтобы не помечать как offline
                    phone.last_seen = datetime.utcnow()
                    logger.info(f"📱 Телефон {phone.mac} ({phone.ip_address}) доступен, но молчит. last_seen обновлен.")
                else:
                    # Телефон действительно недоступен
                    logger.warning(f" Телефон {phone.mac} ({phone.ip_address}) переведен в offline (недоступен > {OFFLINE_TIMEOUT_MINUTES} мин.)")
                    phone.status = "offline"
            
            if offline_candidates:
                db.commit()
                
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка в фоновых задачах: {e}")