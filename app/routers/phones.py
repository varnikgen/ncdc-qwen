from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models import Phone, Account
from app.services.push_service import trigger_phone_autop
from app.services.audit import log_action

router = APIRouter(prefix="/phones", tags=["phones"])

@router.post("/{phone_id}/update")
async def update_phone(
    phone_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")
    
    form = await request.form()
    
    # Обновляем основные поля
    phone.model_name = form.get("model_name")
    phone.override_dss_keys = form.get("override_dss_keys") == "on"
    
    # Обновляем аккаунты
    account_ids_str = form.get("account_ids", "")
    if account_ids_str:
        phone.account_ids = [int(x.strip()) for x in account_ids_str.split(",") if x.strip()]
    else:
        phone.account_ids = []
    
    primary_id = form.get("primary_account_id")
    phone.primary_account_id = int(primary_id) if primary_id else None
    
    # Custom DSS keys
    if phone.override_dss_keys:
        custom_dss = form.get("custom_dss_keys", "[]")
        phone.custom_dss_keys = json.loads(custom_dss)
    else:
        phone.custom_dss_keys = None
    
    # Custom config (Key-Value)
    custom_config = {}
    for key, value in form.items():
        if key.startswith("custom_") and value:
            config_key = key.replace("custom_", "")
            custom_config[config_key] = value
    phone.custom_config = custom_config
    
    db.commit()
    db.refresh(phone)
    
    # Логирование
    log_action(db, "UPDATE_PHONE", "Phone", phone.id, "admin", f"Updated phone {phone.mac}")
    
    # 🚀 PUSH-ОБНОВЛЕНИЕ: Если телефон онлайн, отправляем команду AutoP
    if phone.ip_address and phone.status in ["online", "dnd"]:
        await trigger_phone_autop(phone.ip_address)
    
    return {"status": "success", "message": f"Phone {phone.mac} updated and AutoP triggered"}