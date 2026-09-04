from fastapi import APIRouter, Depends, HTTPException, Request, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
import json

from app.database import get_db
from app.models import Phone, Account, PhoneModel, AuditLog
from app.services.push_service import trigger_phone_autop
from app.services.audit import log_action

router = APIRouter(prefix="/phones", tags=["phones"])

@router.get("/")
async def list_phones(request: Request, db: Session = Depends(get_db)):
    # Получаем статистику и список телефонов
    phones = db.query(Phone).order_by(Phone.last_seen.desc()).all()
    
    # Статистика для карточек
    total = db.query(Phone).count()
    online = db.query(Phone).filter(Phone.status == "online").count()
    offline = db.query(Phone).filter(Phone.status.in_(["offline", "unregistered"])).count()
    
    return request.app.state.templates.TemplateResponse("phones/list.html", {
        "request": request,
        "phones": phones,
        "stats": {"total": total, "online": online, "offline": offline}
    })

@router.get("/{phone_id}/edit")
async def edit_phone(request: Request, phone_id: int, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Телефон не найден")
    
    accounts = db.query(Account).all()
    models = db.query(PhoneModel).all()
    
    # Определяем, какие DSS-клавиши показывать
    if phone.override_dss_keys and phone.custom_dss_keys:
        # Сортируем по номеру линии
        current_dss = sorted(phone.custom_dss_keys, key=lambda x: x.get('line', 0))
        inherit_from_account = False
    elif phone.primary_account_id:
        primary_acc = db.query(Account).filter(Account.id == phone.primary_account_id).first()
        raw_dss = primary_acc.dss_keys if primary_acc else []
        current_dss = sorted(raw_dss, key=lambda x: x.get('line', 0))
        inherit_from_account = True
    else:
        current_dss = []
        inherit_from_account = False
    
    # Количество аккаунтов, привязанных к телефону
    phone_account_count = len(phone.account_ids) if phone.account_ids else 0
    
    return request.app.state.templates.TemplateResponse("phones/edit.html", {
        "request": request,
        "phone": phone,
        "accounts": accounts,
        "models": models,
        "current_dss": current_dss,
        "inherit_from_account": inherit_from_account,
        "phone_account_count": phone_account_count
    })

@router.post("/{phone_id}/update")
async def update_phone(
    request: Request, 
    phone_id: int, 
    db: Session = Depends(get_db)
):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Телефон не найден")
    
    form = await request.form()
    
    print(f"\n=== DEBUG: Полученные данные формы ===")
    print(f"custom_dss_keys: {form.get('custom_dss_keys')}")
    print(f"======================================\n")
    
    phone.model_name = form.get("model_name")
    phone.override_dss_keys = form.get("override_dss_keys") == "on"
    
    # Парсим аккаунты (строка вида "1,2,3")
    acc_ids_str = form.get("account_ids", "")
    phone.account_ids = [int(x.strip()) for x in acc_ids_str.split(",") if x.strip()] if acc_ids_str else []
    
    primary_id = form.get("primary_account_id")
    phone.primary_account_id = int(primary_id) if primary_id else None
    
    # DSS клавиши
    if phone.override_dss_keys:
        custom_dss = form.get("custom_dss_keys", "[]")
        print(f"DEBUG: Парсим custom_dss_keys: {custom_dss}")
        try:
            phone.custom_dss_keys = json.loads(custom_dss)
            print(f"DEBUG: Распарсенные DSS keys: {phone.custom_dss_keys}")
        except json.JSONDecodeError as e:
            print(f"DEBUG: Ошибка парсинга JSON: {e}")
            phone.custom_dss_keys = []
    else:
        phone.custom_dss_keys = None
    
    # Custom config (Key-Value) - ИСКЛЮЧАЕМ служебные поля
    custom_config = {}
    for key, value in form.items():
        if key.startswith("custom_") and key not in ["custom_dss_keys", "custom_config"] and value:
            custom_config[key.replace("custom_", "")] = value
    phone.custom_config = custom_config
    
    db.commit()
    db.refresh(phone)
    
    log_action(db, "UPDATE_PHONE", "Phone", phone.id, "admin", f"Updated phone {phone.mac}")
    
    # Push-обновление
    if phone.ip_address and phone.status in ["online", "dnd"]:
        print(f"\n[DEBUG PUSH] запуск AutoP. IP: {phone.ip_address}, Status: {phone.status}\n")
        await trigger_phone_autop(db, phone.id)
    else:
        print(f"\n[DEBUG PUSH] Пропуск AutoP. IP: {phone.ip_address}, Status: {phone.status}\n")
    
    return {"status": "success", "message": f"Телефон {phone.mac} успешно обновлен"}

@router.get("/{phone_id}/dss-keys")
async def get_dss_keys(request: Request, phone_id: int, db: Session = Depends(get_db)):
    phone = db.query(Phone).filter(Phone.id == phone_id).first()
    if not phone:
        raise HTTPException(status_code=404, detail="Phone not found")
    
    if phone.primary_account_id:
        primary_acc = db.query(Account).filter(Account.id == phone.primary_account_id).first()
        raw_dss = primary_acc.dss_keys if primary_acc else []
        current_dss = sorted(raw_dss, key=lambda x: x.get('line', 0))
    else:
        current_dss = []
    
    phone_account_count = len(phone.account_ids) if phone.account_ids else 0
    
    return request.app.state.templates.TemplateResponse("phones/_dss_keys_table.html", {
        "request": request,
        "current_dss": current_dss,
        "phone_account_count": phone_account_count
    })