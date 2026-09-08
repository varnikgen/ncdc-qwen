from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.database import get_db
from app.models import Phone

router = APIRouter(prefix="/actions", tags=["actions"])
logger = logging.getLogger("ncdc.actions")

@router.get("/")
async def handle_action_url(
    request: Request,
    db: Session = Depends(get_db)
):
    """Обработка Action URI запросов от телефонов Yealink"""
    
    # 1. Получаем IP телефона (учитываем проксирование через Nginx)
    client_ip = request.client.host
    if request.headers.get("x-forwarded-for"):
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
    
    # 2. Пытаемся извлечь MAC-адрес из User-Agent или параметров запроса
    # Пример User-Agent: "Yealink SIP-T46U 108.87.14.1 24:9a:d8:6e:9d:88"
    user_agent = request.headers.get("user-agent", "")
    mac = request.query_params.get("mac", "").replace(":", "").upper()
    
    if not mac and user_agent:
        # Простой парсинг MAC из конца User-Agent (последние 12 hex символов)
        import re
        match = re.search(r'([0-9A-Fa-f]{2}[:-]?){5}([0-9A-Fa-f]{2})$', user_agent.replace(" ", ""))
        if match:
            mac = match.group(0).replace(":", "").replace("-", "").upper()

    if not mac or len(mac) != 12:
        logger.warning(f"Не удалось определить MAC из запроса. UA: {user_agent}, IP: {client_ip}")
        return {"status": "ignored", "reason": "Unknown MAC"}

    # 3. Находим телефон в БД
    phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
    if not phone:
        logger.warning(f"Телефон с MAC {mac} не найден в БД")
        return {"status": "ignored", "reason": "Phone not found"}

    # 4. БЕЗУСЛОВНО обновляем last_seen и ip_address при любом обращении
    phone.ip_address = client_ip
    phone.last_seen = datetime.utcnow()
    
    # Опционально: обновляем статус, если пришел конкретный event (например, registered)
    event = request.query_params.get("event", "")
    if event == "registered":
        phone.status = "online"
    elif event == "unregistered":
        phone.status = "unregistered"
    # Если event другой (например, outgoing_call), статус не меняем, но last_seen обновился!

    db.commit()
    logger.info(f"✅ Action URL от {mac} (IP: {client_ip}, Event: {event}) обработан, last_seen обновлен.")
    
    return {"status": "success"}