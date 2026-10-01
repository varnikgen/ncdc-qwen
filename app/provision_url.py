"""URL провижининга, в том числе с user:pass для заводского сброса."""
from urllib.parse import quote, urlparse, urlunparse

from app.config import settings
from app.security import quote_cfg


def provision_http_url(filename: str = "", with_auth: bool = False) -> str:
    parsed = urlparse(settings.base_url)
    host = parsed.hostname or "localhost"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    if with_auth and settings.PROVISION_AUTH_ENABLED and settings.PROVISION_USER:
        user = quote(settings.PROVISION_USER, safe="")
        password = quote(settings.PROVISION_PASS, safe="")
        netloc = f"{user}:{password}@{netloc}"
    path = "/provision/" + filename.lstrip("/")
    return urlunparse((parsed.scheme or "https", netloc, path, "", "", ""))


def _web_password_line() -> str | None:
    """Чтобы после reset не всплыл мастер «смените admin»."""
    password = (settings.PHONE_WEB_PASSWORD or "").strip()
    if not password or password == "admin":
        return None
    user = (settings.PHONE_WEB_USER or "admin").strip() or "admin"
    return f"security.user_password = {quote_cfg(f'{user}:{password}')}"


def bootstrap_cfg_body() -> str:
    """Минимальный cfg: учётки провижининга и пароль веб-UI, без SIP/LDAP.

    Заводской сброс: трубка ещё не знает Basic. Этот файл она применит,
    сменит URL на user:pass@host и повторит запрос уже с паролем.
    """
    lines = [
        "#!version:1.0.0.1",
        f"static.auto_provision.server.url = {provision_http_url(with_auth=True)}",
        "static.auto_provision.power_on = 1",
        "static.auto_provision.repeat.enable = 1",
        "static.auto_provision.repeat.minutes = 1",
    ]
    if settings.PROVISION_AUTH_ENABLED and settings.PROVISION_USER:
        lines.append(f"static.auto_provision.username = {settings.PROVISION_USER}")
        lines.append(f"static.auto_provision.password = {quote_cfg(settings.PROVISION_PASS)}")
    web = _web_password_line()
    if web:
        lines.append(web)
    return "\n".join(lines) + "\n"


def boot_file_body() -> str:
    auth = settings.PROVISION_AUTH_ENABLED and bool(settings.PROVISION_USER)
    lines = [
        "#!version:1.0.0.1",
        f"overwrite_mode = {int(settings.BOOT_OVERWRITE_MODE)}",
    ]
    if auth:
        lines.append(f"static.auto_provision.username = {settings.PROVISION_USER}")
        lines.append(f"static.auto_provision.password = {quote_cfg(settings.PROVISION_PASS)}")
        y000 = provision_http_url("y000000000000.cfg", with_auth=True)
        pn = provision_http_url("$PN.cfg", with_auth=True)
        mac = provision_http_url("$MAC.cfg", with_auth=True)
        lines.append(f'include:config "{y000}"')
        lines.append(f'include:config "{pn}"')
        lines.append(f'include:config "{mac}"')
    else:
        lines.append('include:config "y000000000000.cfg"')
        lines.append('include:config "$PN.cfg"')
        lines.append('include:config "$MAC.cfg"')
    web = _web_password_line()
    if web:
        lines.append(web)
    return "\n".join(lines) + "\n"
