from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models import PhoneModel, AuditLog
from app.services.audit import log_action

router = APIRouter(prefix="/models", tags=["models"])

@router.get("/")
async def list_models(request: Request, db: Session = Depends(get_db)):
    models = db.query(PhoneModel).order_by(PhoneModel.name).all()
    
    return request.app.state.templates.TemplateResponse("models/list.html", {
        "request": request,
        "models": models
    })

@router.get("/new")
async def new_model(request: Request):
    return request.app.state.templates.TemplateResponse("models/edit.html", {
        "request": request,
        "model": None,
        "default_config_json": "{}"
    })

@router.post("/")
async def create_model(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    
    # Парсим JSON для default_config
    try:
        default_config = json.loads(form.get("default_config", "{}"))
    except json.JSONDecodeError:
        default_config = {}

    model = PhoneModel(
        name=form.get("name").strip().upper(),
        max_accounts=int(form.get("max_accounts", 12)),
        max_dss_keys=int(form.get("max_dss_keys", 40)),
        firmware_url=form.get("firmware_url", ""),
        ieee802_1x_enable=form.get("ieee802_1x_enable") == "on",
        ieee802_1x_identity=form.get("ieee802_1x_identity", ""),
        ieee802_1x_mode=int(form.get("ieee802_1x_mode", 0)),
        ieee802_1x_root_cert_url=form.get("ieee802_1x_root_cert_url", ""),
        ieee802_1x_client_cert_url=form.get("ieee802_1x_client_cert_url", ""),
        ieee802_1x_upload_mode=int(form.get("ieee802_1x_upload_mode", 0)),
        default_config=default_config
    )
    
    db.add(model)
    db.commit()
    db.refresh(model)
    
    log_action(db, "CREATE_MODEL", "PhoneModel", model.id, "admin", f"Created model {model.name}")
    
    return {"status": "success", "message": f"Модель {model.name} создана", "redirect": "/models"}

@router.get("/{model_id}/edit")
async def edit_model(request: Request, model_id: int, db: Session = Depends(get_db)):
    model = db.query(PhoneModel).filter(PhoneModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    
    default_config_json = json.dumps(model.default_config, indent=2) if model.default_config else "{}"
    
    return request.app.state.templates.TemplateResponse("models/edit.html", {
        "request": request,
        "model": model,
        "default_config_json": default_config_json
    })

@router.post("/{model_id}/update")
async def update_model(request: Request, model_id: int, db: Session = Depends(get_db)):
    model = db.query(PhoneModel).filter(PhoneModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    
    form = await request.form()
    
    try:
        default_config = json.loads(form.get("default_config", "{}"))
    except json.JSONDecodeError:
        default_config = model.default_config # Сохраняем старое, если новый JSON невалиден

    model.name = form.get("name").strip().upper()
    model.max_accounts = int(form.get("max_accounts", 12))
    model.max_dss_keys = int(form.get("max_dss_keys", 40))
    model.firmware_url = form.get("firmware_url", "")
    model.ieee802_1x_enable = form.get("ieee802_1x_enable") == "on"
    model.ieee802_1x_identity = form.get("ieee802_1x_identity", "")
    model.ieee802_1x_mode = int(form.get("ieee802_1x_mode", 0))
    model.ieee802_1x_root_cert_url = form.get("ieee802_1x_root_cert_url", "")
    model.ieee802_1x_client_cert_url = form.get("ieee802_1x_client_cert_url", "")
    model.ieee802_1x_upload_mode = int(form.get("ieee802_1x_upload_mode", 0))
    model.default_config = default_config
    
    db.commit()
    db.refresh(model)
    
    log_action(db, "UPDATE_MODEL", "PhoneModel", model.id, "admin", f"Updated model {model.name}")
    
    return {"status": "success", "message": f"Модель {model.name} обновлена", "redirect": "/models"}

@router.post("/{model_id}/delete")
async def delete_model(request: Request, model_id: int, db: Session = Depends(get_db)):
    model = db.query(PhoneModel).filter(PhoneModel.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    
    model_name = model.name
    db.delete(model)
    db.commit()
    
    log_action(db, "DELETE_MODEL", "PhoneModel", model_id, "admin", f"Deleted model {model_name}")
    
    return {"status": "success", "message": f"Модель {model_name} удалена", "redirect": "/models"}