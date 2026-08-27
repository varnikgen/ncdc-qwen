from fastapi import APIRouter, Response, Depends, HTTPException
from sqlalchemy.orm import Session
from jinja2 import Environment, FileSystemLoader
import os
import re

from app.database import get_db
from app.models import PhoneModel, GlobalConfig
from app.services.config_builder import get_merged_config

router = APIRouter(prefix="/provision", tags=["provisioning"])

templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "provision")
jinja_env = Environment(loader=FileSystemLoader(templates_dir), trim_blocks=True, lstrip_blocks=True)

# Регулярное выражение для проверки MAC-адреса (ровно 12 hex-символов)
MAC_PATTERN = re.compile(r'^[0-9a-fA-F]{12}$')

@router.get("/y000000000000.boot")
@router.get("/{mac}.boot")
async def get_boot_file(mac: str = "y000000000000"):
    boot_content = """#!version:1.0.0.1
overwrite_mode = 0
include:config "y000000000000.cfg"
include:config "$PN.cfg"
include:config "$MAC.cfg"
"""
    return Response(content=boot_content, media_type="text/plain")

@router.get("/y000000000000.cfg")
async def get_global_config(db: Session = Depends(get_db)):
    global_cfg = db.query(GlobalConfig).first()
    config = global_cfg.settings.copy() if global_cfg and global_cfg.settings else {}
    template = jinja_env.get_template("y000000000000.cfg.j2")
    rendered = template.render(config=config)
    return Response(content=rendered, media_type="text/plain")

# ЕДИНЫЙ маршрут для всех .cfg файлов с явной проверкой
@router.get("/{identifier}.cfg")
async def get_config(identifier: str, db: Session = Depends(get_db)):
    """
    Универсальный обработчик:
    - Если identifier - это MAC-адрес (12 hex-символов), отдаём конфиг телефона
    - Иначе отдаём конфиг модели
    """
    
    # Проверяем, является ли identifier MAC-адресом
    if MAC_PATTERN.match(identifier):
        # Это телефон
        print(f"\n✅ DEBUG: ROUTED TO PHONE CONFIG === MAC: {identifier}\n")
        config_data = get_merged_config(db, identifier)
        template = jinja_env.get_template("phone.cfg.j2")
        rendered = template.render(config=config_data)
        return Response(content=rendered, media_type="text/plain")
    else:
        # Это модель
        print(f"\n⚙️ DEBUG: ROUTED TO MODEL CONFIG === Model: {identifier}\n")
        model_obj = db.query(PhoneModel).filter(PhoneModel.name == identifier.upper()).first()
        config = {}
        
        if model_obj:
            config["model_firmware_url"] = model_obj.firmware_url
            config["model_802_1x_enable"] = model_obj.ieee802_1x_enable
            config["model_802_1x_identity"] = model_obj.ieee802_1x_identity
            config["model_802_1x_mode"] = model_obj.ieee802_1x_mode
            config["model_802_1x_root_cert_url"] = model_obj.ieee802_1x_root_cert_url
            config["model_802_1x_client_cert_url"] = model_obj.ieee802_1x_client_cert_url
            if model_obj.default_config:
                config.update(model_obj.default_config)
                
        config["model_name"] = identifier.upper()
        template = jinja_env.get_template("model.cfg.j2")
        rendered = template.render(config=config)
        return Response(content=rendered, media_type="text/plain")