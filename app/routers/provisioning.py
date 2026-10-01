"""Выдача Yealink cfg.

После заводского сброса трубка ещё не знает Basic → 401
«Invalid provisioning credential». .boot и (при PROVISION_BOOTSTRAP)
минимальный cfg без SIP отдаём без пароля; в них пишем username/password
провижининга и URL с user:pass. Следующий запрос уже с Basic.
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
from app.provision_url import boot_file_body, bootstrap_cfg_body
from app.security import MAC_RE, normalize_mac
from app.phone_ip import pick_phone_ip, reported_phone_ip
from app.services.config_builder import build_phone_config, build_model_config
from app.services.audit import log_action

router = APIRouter(prefix="/provision", tags=["provisioning"])
logger = logging.getLogger("ncdc.provision")


def _unauthorized() -> None:
    raise HTTPException(
        status_code=401,
        detail="Provisioning credentials required",
        headers={"WWW-Authenticate": 'Basic realm="NCDC Provisioning"'},
    )


def _full_cfg_or_bootstrap(request: Request) -> Response | None:
    """None = можно отдать полный cfg. Иначе — ответ-bootstrap или 401."""
    if provision_authorized(request):
        return None
    if settings.PROVISION_BOOTSTRAP:
        return Response(content=bootstrap_cfg_body(), media_type="text/plain")
    _unauthorized()


def _touch_phone(db, phone: Phone, request: Request) -> None:
    """last_seen с каждого cfg. IP только из $ip или уже сохранённый LAN."""
    chosen = pick_phone_ip(reported_phone_ip(request), None, phone.ip_address)
    phone.ip_address = chosen
    phone.last_seen = datetime.utcnow()
    db.commit()


def _render(name: str, context: dict) -> Response:
    template = jinja_env.get_template(name)
    return Response(content=template.render(**context), media_type="text/plain")


@router.get("/y000000000000.boot")
@router.get("/{mac}.boot")
async def get_boot_file(mac: str = "y000000000000"):
    """Без Basic: после reset трубка ещё не знает пароль. Секретов SIP здесь нет."""
    return Response(content=boot_file_body(), media_type="text/plain")


@router.get("/y000000000000.cfg")
async def get_global_config(request: Request, db: Session = Depends(get_db)):
    bootstrap = _full_cfg_or_bootstrap(request)
    if bootstrap is not None:
        return bootstrap
    global_cfg = db.query(GlobalConfig).first()
    cfg_settings = global_cfg.settings if global_cfg and global_cfg.settings else {}
    return _render("y000000000000.cfg.j2", {"config": {"global": cfg_settings}})


@router.get("/{identifier}.cfg")
async def get_config(identifier: str, request: Request, db: Session = Depends(get_db)):
    """12 hex → phone cfg; иначе считаем identifier именем модели ($PN)."""
    bootstrap = _full_cfg_or_bootstrap(request)
    if bootstrap is not None:
        return bootstrap

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
