import asyncio
import ipaddress
import logging
import re
import httpx
from sqlalchemy.orm import Session

from app.models import Phone
from app.security import normalize_mac
from app.services.audit import log_action

logger = logging.getLogger("ncdc.scanner")

async def scan_subnet(subnet: str, username: str, password: str, db: Session, admin_user: str):
    """Сканирует подсеть на наличие телефонов Yealink и добавляет их в БД."""
    try:
        network = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        raise ValueError("Неверный формат подсети (например, 10.30.17.0/24)")

    found_phones = []
    enrolled_phones = []
    debug_info = []

    semaphore = asyncio.Semaphore(20)

    async def check_ip(ip_str: str):
        async with semaphore:
            for port in [80, 443]:
                scheme = "https" if port == 443 else "http"
                try:
                    async with httpx.AsyncClient(
                        timeout=5.0,
                        verify=False,
                        follow_redirects=True  # Важно для редиректов после логина
                    ) as client:
                        url = f"{scheme}://{ip_str}:{port}/"
                        
                        # 1. Проверяем корневую страницу
                        response = await client.get(url)
                        
                        www_auth = response.headers.get("www-authenticate", "").lower()
                        server_header = response.headers.get("server", "").lower()
                        is_yealink = False
                        
                        # Определяем Yealink по различным признакам
                        if response.status_code == 401 and "yealink" in www_auth:
                            is_yealink = True
                        elif "yealink" in server_header:
                            is_yealink = True
                        elif response.status_code == 200 and "yealink" in response.text.lower():
                            is_yealink = True
                        
                        if is_yealink:
                            mac = "UNKNOWN"
                            
                            # 2. Пытаемся получить MAC разными способами
                            
                            # Способ A: HTTP Basic Auth (если есть www-authenticate)
                            if response.status_code == 401:
                                try:
                                    auth_resp = await client.get(
                                        f"{scheme}://{ip_str}:{port}/cgi-bin/ConfigManApp.com",
                                        auth=(username, password),
                                        timeout=5.0
                                    )
                                    if auth_resp.status_code == 200:
                                        match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', auth_resp.text)
                                        if match:
                                            mac = normalize_mac(match.group(0))
                                except Exception as e:
                                    logger.debug(f"Basic auth failed on {ip_str}: {e}")
                            
                            # Способ B: HTML форма входа (POST запрос)
                            elif response.status_code == 200:
                                try:
                                    # Ищем форму входа в HTML
                                    # Yealink обычно использует форму с action="/login.cgi" или подобным
                                    form_action = None
                                    csrf_token = None
                                    
                                    # Ищем CSRF токен если есть
                                    csrf_match = re.search(r'name=["\']?csrf["\']?\s+value=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
                                    if csrf_match:
                                        csrf_token = csrf_match.group(1)
                                    
                                    # Ищем action формы
                                    form_match = re.search(r'<form[^>]+action=["\']([^"\']+)["\']', response.text, re.IGNORECASE)
                                    if form_match:
                                        form_action = form_match.group(1)
                                    
                                    # Если нашли форму, пытаемся войти
                                    if form_action:
                                        login_url = f"{scheme}://{ip_str}:{port}/{form_action}"
                                        login_data = {
                                            'username': username,
                                            'password': password
                                        }
                                        if csrf_token:
                                            login_data['csrf'] = csrf_token
                                        
                                        login_resp = await client.post(
                                            login_url,
                                            data=login_data,
                                            timeout=5.0
                                        )
                                        
                                        # После успешного входа перенаправляет на страницу статуса
                                        if login_resp.status_code in [200, 302]:
                                            # Пробуем получить страницу статуса
                                            status_urls = [
                                                f"{scheme}://{ip_str}:{port}/cgi-bin/ConfigManApp.com",
                                                f"{scheme}://{ip_str}:{port}/status",
                                                f"{scheme}://{ip_str}:{port}/index.htm"
                                            ]
                                            
                                            for status_url in status_urls:
                                                try:
                                                    status_resp = await client.get(status_url, timeout=3.0)
                                                    if status_resp.status_code == 200:
                                                        match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', status_resp.text)
                                                        if match:
                                                            mac = normalize_mac(match.group(0))
                                                            break
                                                except:
                                                    continue
                                except Exception as e:
                                    logger.debug(f"Form login failed on {ip_str}: {e}")
                            
                            # Способ C: Пробуем стандартные URL для получения MAC
                            if mac == "UNKNOWN":
                                try:
                                    # Некоторые модели отдают MAC в заголовках или на специальных страницах
                                    mac_urls = [
                                        f"{scheme}://{ip_str}:{port}/cgi-bin/ConfigManApp.com",
                                        f"{scheme}://{ip_str}:{port}/report/log.htm",
                                    ]
                                    
                                    for mac_url in mac_urls:
                                        try:
                                            mac_resp = await client.get(mac_url, auth=(username, password), timeout=3.0)
                                            if mac_resp.status_code == 200:
                                                match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', mac_resp.text)
                                                if match:
                                                    mac = normalize_mac(match.group(0))
                                                    break
                                        except:
                                            continue
                                except Exception as e:
                                    logger.debug(f"MAC URL scan failed on {ip_str}: {e}")
                            
                            debug_info.append({
                                "ip": ip_str,
                                "port": port,
                                "status": response.status_code,
                                "mac_found": mac,
                                "www_authenticate": www_auth[:50] if www_auth else "",
                            })
                            
                            found_phones.append({
                                "ip": ip_str,
                                "port": port,
                                "mac": mac,
                                "status": response.status_code
                            })
                            
                            # Добавляем в БД
                            if mac != "UNKNOWN":
                                existing = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
                                if not existing:
                                    new_phone = Phone(
                                        mac=mac,
                                        ip_address=ip_str,
                                        status="unregistered",
                                        model_name="Unknown"
                                    )
                                    db.add(new_phone)
                                    db.commit()
                                    db.refresh(new_phone)
                                    enrolled_phones.append({
                                        "ip": ip_str,
                                        "port": port,
                                        "mac": mac,
                                        "id": new_phone.id
                                    })
                                    log_action(
                                        db, "NETWORK_SCAN_ENROLL", "Phone", new_phone.id,
                                        admin_user, f"Enrolled via network scan: {mac} at {ip_str}:{port}"
                                    )
                            else:
                                # MAC не найден, но телефон существует
                                logger.info(f"Found Yealink at {ip_str}:{port} but MAC unknown. "
                                          f"Will be enrolled on first provisioning request.")
                            
                            break  # Нашли на этом порту, не проверяем другой
                            
                except httpx.ConnectError:
                    pass
                except httpx.TimeoutException:
                    pass
                except Exception as e:
                    logger.debug(f"Error checking {ip_str}:{port}: {e}")

    tasks = [check_ip(str(ip)) for ip in network.hosts()]
    await asyncio.gather(*tasks)

    return {
        "total_scanned": len(tasks),
        "found_yealink": len(found_phones),
        "newly_enrolled": len(enrolled_phones),
        "details": enrolled_phones,
        "debug": debug_info
    }
