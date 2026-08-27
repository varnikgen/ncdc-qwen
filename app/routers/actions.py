from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import Phone
from app.services.audit import log_action

router = APIRouter(prefix="/action", tags=["actions"])

# Обработчики для запросов БЕЗ trailing slash
@router.get("")
@router.post("")
# Обработчики для запросов СО trailing slash
@router.get("/")
@router.post("/")
async def handle_action_url(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Обрабатывает Action URL запросы от телефонов Yealink.
    Ожидаемые параметры: mac, ip, event
    """
    # Yealink может отправлять данные через GET (query) или POST (form)
    params = dict(request.query_params)
    if not params:
        form_data = await request.form()
        params = dict(form_data)
    
    mac = params.get("mac", "").replace(":", "").replace("-", "").upper()
    ip = params.get("ip", "")
    event = params.get("event", "unknown")
    
    if not mac or len(mac) != 12:
        raise HTTPException(status_code=400, detail="Invalid or missing MAC address")
    
    # Находим или создаем телефон
    phone = db.query(Phone).filter(Phone.mac == mac).first()
    if not phone:
        phone = Phone(mac=mac, status="offline", account_ids=[])
        db.add(phone)
        db.flush()  # Получаем phone.id для логирования
    
    old_status = phone.status
    new_status = old_status
    
    # Логика обновления статуса на основе события
    if event in ["registered", "register_success"]:
        new_status = "online"
    elif event in ["unregistered", "register_failed"]:
        new_status = "unregistered"
    elif event == "dnd_on":
        new_status = "dnd"
    elif event == "dnd_off":
        new_status = "online" if old_status in ["online", "dnd"] else "offline"
    elif event in ["off_hook", "on_hook", "incoming_call", "call_established"]:
        new_status = "online"
        
    # Обновляем БД только если статус или IP изменились
    if new_status != old_status or not phone.ip_address:
        phone.status = new_status
        if ip:
            phone.ip_address = ip
        phone.last_seen = datetime.utcnow()
        db.commit()
        
        # Логируем событие
        log_action(
            db=db,
            action=f"EVENT_{event.upper()}",
            entity_type="Phone",
            entity_id=phone.id,
            user="system",
            details=f"MAC: {mac}, IP: {ip}, Status: {old_status} -> {new_status}"
        )
    
    return {"status": "success", "mac": mac, "event": event, "new_status": phone.status}