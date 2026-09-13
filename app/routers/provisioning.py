"""Выдача Yealink cfg.

Иерархия, которую трубка запрашивает после .boot:
  y000000000000.cfg  — глобальные параметры
  $PN.cfg            — модель (identifier НЕ похож на MAC)
  $MAC.cfg           — 12 hex-символов → конкретное устройство

Маршрут y000000000000.cfg объявлен выше /{identifier}.cfg, иначе
глобальный файл попал бы в универсальный обработчик.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
import logging

from app.config import settings
from app.database import get_db
from app.middleware.auth import provision_authorized
from app.models import Phone, PhoneModel, GlobalConfig
from app.provision_templates import jinja_env
from app.security import MAC_RE, normalize_mac
from app.services.config_builder import build_phone_config, build_model_config
from app.services.audit import log_action

router = APIRouter(prefix="/provision", tags=["provisioning"])
logger = logging.getLogger("ncdc.provision")


def _require_provision_auth(request: Request) -> None:
    """401 + WWW-Authenticate, чтобы Yealink повторил запрос с Basic."""
    if provision_authorized(request):
        return
    raise HTTPException(
        status_code=401,
        detail="Provisioning credentials required",
        headers={"WWW-Authenticate": 'Basic realm="NCDC Provisioning"'},
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _touch_phone(db, phone: Phone, request: Request) -> None:
    """IP и last_seen с каждого скачивания cfg — иначе AutoP некуда слать."""
    ip = _client_ip(request)
    if ip:
        phone.ip_address = ip
    phone.last_seen = datetime.utcnow()
    db.commit()


def _render(name: str, context: dict) -> Response:
    template = jinja_env.get_template(name)
    return Response(content=template.render(**context), media_type="text/plain")


@router.get("/y000000000000.boot")
@router.get("/{mac}.boot")
async def get_boot_file(request: Request, mac: str = "y000000000000"):
    """Одинаковый boot для всех MAC: Yealink сам подставит $PN и $MAC."""
    _require_provision_auth(request)
    boot_content = (
        "#!version:1.0.0.1\n"
        f"overwrite_mode = {int(settings.BOOT_OVERWRITE_MODE)}\n"
        'include:config "y000000000000.cfg"\n'
        'include:config "$PN.cfg"\n'
        'include:config "$MAC.cfg"\n'
    )
    return Response(content=boot_content, media_type="text/plain")


@router.get("/y000000000000.cfg")
async def get_global_config(request: Request, db: Session = Depends(get_db)):
    _require_provision_auth(request)
    global_cfg = db.query(GlobalConfig).first()
    cfg_settings = global_cfg.settings if global_cfg and global_cfg.settings else {}
    return _render("y000000000000.cfg.j2", {"config": {"global": cfg_settings}})


@router.get("/{identifier}.cfg")
async def get_config(identifier: str, request: Request, db: Session = Depends(get_db)):
    """12 hex → phone cfg; иначе считаем identifier именем модели ($PN)."""
    _require_provision_auth(request)

    if MAC_RE.match(identifier):
        mac = normalize_mac(identifier)
        phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
        if not phone:
            if settings.AUTO_ENROLL:
                phone = Phone(mac=mac, status="unregistered")
                db.add(phone)
                db.commit()
                log_action(db, "AUTO_ENROLL", "Phone", phone.id, "provision", f"Enrolled {mac} via cfg request")
                logger.info("Auto-enrolled phone %s on config request", mac)
            else:
                raise HTTPException(status_code=404, detail="Unknown MAC")
        _touch_phone(db, phone, request)
        try:
            config_data = build_phone_config(db, mac)
        except ValueError:
            raise HTTPException(status_code=404, detail="Unknown MAC")
        return _render("phone.cfg.j2", {"config": config_data})

    model_obj = db.query(PhoneModel).filter(PhoneModel.name == identifier.upper()).first()
    config = build_model_config(model_obj, identifier)
    return _render("model.cfg.j2", {"config": config})
