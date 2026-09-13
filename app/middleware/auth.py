"""Два контура авторизации.

Админка (/phones, /accounts, …) — HTTP Basic из NCDC_ADMIN_*.
Провижининг (/provision) проверяется отдельно через provision_authorized(),
потому что трубки ходят с PROVISION_USER/PASS, а не с админскими.

/actions, /health, /static исключены: телефоны и healthcheck не умеют
логиниться в админку. /actions защищён своим токеном.
"""

from fastapi import Request, status
from fastapi.responses import PlainTextResponse, JSONResponse
import base64
import logging

from app.config import settings
from app.security import constant_time_equals, LoginThrottle

logger = logging.getLogger("ncdc.auth")

ADMIN_EXCLUDED_PREFIXES = (
    "/provision",
    "/health",
    "/actions",
    "/favicon.ico",
    "/static",
)

throttle = LoginThrottle(
    max_failures=settings.LOGIN_MAX_FAILURES,
    lockout_seconds=settings.LOGIN_LOCKOUT_SECONDS,
)


def _client_ip(request: Request) -> str:
    # Nginx ставит X-Forwarded-For = $remote_addr (один hop). Берём первый адрес.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _unauthorized(detail: str = "Unauthorized") -> PlainTextResponse:
    # WWW-Authenticate заставляет браузер показать native Basic-диалог
    return PlainTextResponse(
        detail,
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": 'Basic realm="NCDC Admin Panel"'},
    )


def _decode_basic(auth_header: str) -> tuple[str, str] | None:
    try:
        scheme, credentials = auth_header.split(None, 1)
        if scheme.lower() != "basic":
            return None
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None


def provision_authorized(request: Request) -> bool:
    """True, если провижининг открыт или трубка прислала верный Basic."""
    if not settings.PROVISION_AUTH_ENABLED:
        return True
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False
    parsed = _decode_basic(auth_header)
    if not parsed:
        return False
    username, password = parsed
    return constant_time_equals(username, settings.PROVISION_USER) and constant_time_equals(
        password, settings.PROVISION_PASS
    )


async def basic_auth_middleware(request: Request, call_next):
    path = request.url.path

    if any(path.startswith(prefix) for prefix in ADMIN_EXCLUDED_PREFIXES):
        return await call_next(request)

    ip = _client_ip(request)
    if throttle.is_locked(ip):
        return JSONResponse(
            {"detail": "Too many failed login attempts. Try again later."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return _unauthorized()

    parsed = _decode_basic(auth_header)
    if not parsed:
        return PlainTextResponse("Invalid authorization header", status_code=400)

    username, password = parsed
    user_ok = constant_time_equals(username, settings.NCDC_ADMIN_USER)
    pass_ok = constant_time_equals(password, settings.NCDC_ADMIN_PASS)
    if not (user_ok and pass_ok):
        throttle.record_failure(ip)
        logger.warning("Failed admin login from %s", ip)
        return _unauthorized("Incorrect username or password")

    throttle.record_success(ip)
    request.state.admin_user = username  # попадает в audit log
    return await call_next(request)
