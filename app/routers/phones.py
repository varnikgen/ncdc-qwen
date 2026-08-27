from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
import os
from app.database import get_db
from app.models import Phone, Account, PhoneModel
from app.services.config_builder import get_merged_config
from app.services.push_service import trigger_phone_autop
from app.services.audit import log_action

router = APIRouter(prefix="/phones", tags=["phones"])

@router.get("/")
async def list_phones(
    request: Request,
    db: Session = Depends(get_db),
    search: str = "",
    model: str = "",
    status: str = ""
):
    query = db.query(Phone)
    
    if search:
        query = query.filter(
            (Phone.mac.contains(search)) |
            (Phone.ip_address.contains(search))
        )
    
    if model:
        query = query.filter(Phone.model_name == model)
    
    if status:
        query = query.filter(Phone.status == status)
    
    phones = query.all()
    models = db.query(PhoneModel).all()
    
    template = request.app.state.templates.get_template("phones/list.html")
    return template.render(phones=phones, models=models, search=search)

@router.get("/{phone_id}/edit")
async def edit_phone(
    phone_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")
    
    accounts = db.query(Account).all()
    models = db.query(PhoneModel).all()
    
    # Получаем DSS-клавиши для отображения
    if phone.override_dss_keys and phone.custom_dss_keys:
        current_dss = phone.custom_dss_keys
        inherit_from_account = False
    elif phone.primary_account and phone.primary_account.dss_keys:
        current_dss = phone.primary_account.dss_keys
        inherit_from_account = True
    else:
        current_dss = []
        inherit_from_account = False
    
    template = request.app.state.templates.get_template("phones/edit.html")
    return template.render(
        phone=phone,
        accounts=accounts,
        models=models,
        current_dss=current_dss,
        inherit_from_account=inherit_from_account
    )

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
    
    # Обновляем аккаунты (список ID через запятую)
    account_ids_str = form.get("account_ids", "")
    if account_ids_str:
        phone.account_ids = [int(x.strip()) for x in account_ids_str.split(",") if x.strip()]
    else:
        phone.account_ids = []
    
    # Первичный аккаунт
    primary_id = form.get("primary_account_id")
    phone.primary_account_id = int(primary_id) if primary_id else None
    
    # Custom DSS keys (если override включён)
    if phone.override_dss_keys:
        # Парсим JSON из формы
        custom_dss = form.get("custom_dss_keys", "[]")
        import json
        phone.custom_dss_keys = json.loads(custom_dss)
    else:
        phone.custom_dss_keys = None
    
    # Custom config (key-value pairs)
    custom_config = {}
    for key, value in form.items():
        if key.startswith("custom_") and value:
            config_key = key.replace("custom_", "")
            custom_config[config_key] = value
    phone.custom_config = custom_config
    
    db.commit()
    db.refresh(phone)
    
    # Логирование
    await log_action(db, "UPDATE_PHONE", "Phone", phone.id, "system", 
                    f"Updated phone {phone.mac}")
    
    # Push-обновление если телефон онлайн
    if phone.ip_address and phone.status == "online":
        await trigger_phone_autop(phone.ip_address)
    
    return {"status": "success", "message": "Phone updated"}