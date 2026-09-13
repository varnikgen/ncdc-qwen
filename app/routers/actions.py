"""Action URI: трубка сама стучится при register / DND / unregistered.

Защита — query-параметр token (не Basic): Yealink подставляет его в URL
из глобального cfg. Без токена любой мог бы подменить IP устройства
и затем отправить AutoP на чужой адрес.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.config import settings
from app.database import get_db
from app.models import Phone
from app.security import extract_mac, constant_time_equals
from app.services.audit import log_action

router = APIRouter(prefix="/actions", tags=["actions"])
logger = logging.getLogger("ncdc.actions")

DND_ON_EVENTS = {"dnd_on", "dndon", "DNDOn"}
DND_OFF_EVENTS = {"dnd_off", "dndoff", "DNDOff"}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/")
@router.post("/")
async def handle_action_url(request: Request, db: Session = Depends(get_db)):
    """Обновляет last_seen/IP/статус. При AUTO_ENROLL создаёт Phone."""
    token = request.query_params.get("token", "")
    if not settings.ACTION_URI_TOKEN or not constant_time_equals(token, settings.ACTION_URI_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid action token")

    client_ip = _client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    mac = extract_mac(user_agent, request.query_params.get("mac", ""))

    if not mac:
        logger.warning("Action URL ignored: MAC not found (UA=%s IP=%s)", user_agent, client_ip)
        return {"status": "ignored", "reason": "Unknown MAC"}

    phone = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
    created = False
    if not phone:
        if not settings.AUTO_ENROLL:
            logger.warning("Action URL for unknown MAC %s", mac)
            return {"status": "ignored", "reason": "Phone not found"}
        phone = Phone(mac=mac, status="unregistered")
        db.add(phone)
        created = True

    if client_ip:
        phone.ip_address = client_ip
    phone.last_seen = datetime.utcnow()

    event = request.query_params.get("event", "")
    event_norm = event.lower().replace(" ", "_").replace("-", "_")
    if event_norm in {"registered", "setup_complete", "setup_completed", "reged", "register"}:
        phone.status = "online"
    elif event_norm in {"unregistered", "registration_failed", "register_failed"}:
        phone.status = "unregistered"
    elif event in DND_ON_EVENTS or event_norm in DND_ON_EVENTS:
        phone.status = "dnd"
    elif event in DND_OFF_EVENTS or event_norm in DND_OFF_EVENTS:
        phone.status = "online"

    db.commit()
    if created:
        log_action(db, "AUTO_ENROLL", "Phone", phone.id, "action-uri", f"Enrolled {mac} from {client_ip}")
    logger.info("Action URL %s MAC=%s IP=%s event=%s", "created" if created else "updated", mac, client_ip, event)
    return {"status": "success", "mac": mac, "created": created}
