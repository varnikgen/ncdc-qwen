import asyncio
import logging
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import AuditLog

# Используем логгер uvicorn, чтобы сообщения точно попали в общий лог
logger = logging.getLogger("uvicorn.error")

# Настройка: сколько дней хранить логи
RETENTION_DAYS = 90 

async def cleanup_audit_logs_task():
    # print гарантированно выведет текст в консоль контейнера
    print(f"🕒 [AUDIT CLEANUP] Запущена фоновая задача очистки логов (хранение: {RETENTION_DAYS} дней)")
    logger.info(f"Запущена фоновая задача очистки логов аудита (хранение: {RETENTION_DAYS} дней)")
    
    while True:
        # Ждем 24 часа (86400 секунд)
        await asyncio.sleep(86400)
        
        try:
            db = SessionLocal()
            cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
            
            result = db.query(AuditLog).filter(AuditLog.timestamp < cutoff_date).delete()
            db.commit()
            
            if result > 0:
                print(f"✅ [AUDIT CLEANUP] Автоматически удалено {result} старых записей")
                logger.info(f"Автоматически удалено {result} старых записей аудита (старше {RETENTION_DAYS} дней)")
            else:
                print("ℹ️ [AUDIT CLEANUP] Старых записей для удаления не найдено")
                
            db.close()
        except Exception as e:
            print(f"❌ [AUDIT CLEANUP] Ошибка при очистке: {e}")
            logger.error(f"Ошибка при автоматической очистке логов аудита: {e}")