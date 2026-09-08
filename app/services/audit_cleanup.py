import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import AuditLog, Phone

logger = logging.getLogger("uvicorn.error")

RETENTION_DAYS = 90 
OFFLINE_TIMEOUT_MINUTES = 5 

async def background_tasks():
    print(f"🕒 [BACKGROUND] Запущены фоновые задачи (Аудит: {RETENTION_DAYS} дн., Статусы: {OFFLINE_TIMEOUT_MINUTES} мин.)")
    logger.info("Запущены фоновые задачи обслуживания системы")
    
    while True:
        # Ждем 60 секунд между циклами проверки
        await asyncio.sleep(60)
        
        try:
            db = SessionLocal()
            
            # --- ЗАДАЧА 1: Очистка старых логов (раз в сутки можно делать, но проверка каждый цикл безопасна) ---
            cutoff_audit = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
            deleted_logs = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_audit).delete()
            if deleted_logs > 0:
                logger.info(f"🧹 Удалено {deleted_logs} старых записей аудита")
            
            # --- ЗАДАЧА 2: Перевод телефонов в offline ---
            cutoff_phone = datetime.utcnow() - timedelta(minutes=OFFLINE_TIMEOUT_MINUTES)
            # Находим телефоны, которые были online/dnd, но не присылали сигналы дольше timeout
            offline_phones = db.query(Phone).filter(
                Phone.status.in_(["online", "dnd"]),
                Phone.last_seen < cutoff_phone
            ).all()
            
            for phone in offline_phones:
                logger.warning(f"📉 Телефон {phone.mac} ({phone.ip_address}) переведен в offline (нет сигнала > {OFFLINE_TIMEOUT_MINUTES} мин.)")
                phone.status = "offline"
                
            if offline_phones:
                db.commit()
                
            db.close()
            
        except Exception as e:
            logger.error(f"❌ Ошибка в фоновых задачах: {e}")