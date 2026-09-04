import httpx
import logging
from sqlalchemy.orm import Session
from app.models import Phone

logger = logging.getLogger("ncdc.push_service")

async def trigger_phone_autop(db: Session, phone_id: int) -> bool:
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    print(f"\n[DEBUG PUSH] запуск AutoP. ID: {phone_id}")
    
    if not phone:
        logger.warning("Невозможно отправить AutoP: телефон не найден.")
        return False
        
    if not phone.ip_address:
        logger.warning(f"⚠️ AutoP пропущен: у телефона {phone.mac} не указан IP-адрес в БД.")
        return False
        
    if phone.status not in ["online", "dnd"]:
        logger.warning(f"⚠️ AutoP пропущен: статус телефона {phone.mac} = {phone.status} (требуется online или dnd).")
        return False

    url = f"https://{phone.ip_address}/servlet?key=AutoP"
    
    # Берем только из БД, без хардкода. Если там NULL, будет ошибка, и мы об этом узнаем.
    username = phone.admin_username
    password = phone.admin_password
    
    if not username or not password:
        logger.error(f"❌ AutoP пропущен: у телефона {phone.mac} не заданы admin_username или admin_password в БД.")
        return False

    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            verify=False, # Игнорируем самоподписанные сертификаты телефона
            auth=(username, password)
        ) as client:
            response = await client.get(url)
            if response.status_code == 200:
                logger.info(f"✅ AutoP успешно отправлен на {phone.ip_address} (MAC: {phone.mac})")
                return True
            else:
                logger.warning(f"⚠️ AutoP вернул статус {response.status_code} для {phone.ip_address}")
                return False
    except Exception as exc:
        logger.error(f"❌ Ошибка при отправке AutoP на {phone.ip_address}: {exc}")
        return False