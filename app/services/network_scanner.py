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

    # Ограничиваем одновременные запросы
    semaphore = asyncio.Semaphore(20)  # Уменьшили с 50 до 20 для стабильности

    async def check_ip(ip_str: str):
        async with semaphore:
            # Проверяем оба порта: HTTP (80) и HTTPS (443)
            for port in [80, 443]:
                scheme = "https" if port == 443 else "http"
                try:
                    async with httpx.AsyncClient(
                        timeout=5.0,  # Увеличили таймаут с 2 до 5 секунд
                        verify=False,
                        follow_redirects=False
                    ) as client:
                        url = f"{scheme}://{ip_str}:{port}/"
                        response = await client.get(url)
                        
                        www_auth = response.headers.get("www-authenticate", "").lower()
                        server_header = response.headers.get("server", "").lower()
                        
                        # Логируем для отладки
                        debug_info.append({
                            "ip": ip_str,
                            "port": port,
                            "status": response.status_code,
                            "www_authenticate": www_auth,
                            "server": server_header
                        })
                        
                        # Проверяем признаки Yealink
                        is_yealink = False
                        if response.status_code == 401 and "yealink" in www_auth:
                            is_yealink = True
                        elif "yealink" in server_header:
                            is_yealink = True
                        elif response.status_code == 200 and "yealink" in response.text.lower():
                            is_yealink = True
                        
                        if is_yealink:
                            mac = "UNKNOWN"
                            
                            # Пытаемся авторизоваться и получить MAC
                            try:
                                auth_resp = await client.get(
                                    f"{scheme}://{ip_str}:{port}/cgi-bin/ConfigManApp.com",
                                    auth=(username, password),
                                    timeout=5.0
                                )
                                if auth_resp.status_code == 200:
                                    # Ищем MAC в HTML
                                    match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', auth_resp.text)
                                    if match:
                                        mac = normalize_mac(match.group(0))
                            except Exception as e:
                                logger.debug(f"Failed to auth on {ip_str}:{port}: {e}")
                            
                            found_phones.append({
                                "ip": ip_str,
                                "port": port,
                                "mac": mac,
                                "status": response.status_code
                            })
                            
                            # Добавляем в БД если MAC известен
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
                                    logger.info(f"Phone {mac} already exists in DB")
                            
                            break  # Если нашли на одном порту, не проверяем другой
                            
                except httpx.ConnectError:
                    pass  # Порт закрыт или недоступен
                except httpx.TimeoutException:
                    pass  # Таймаут
                except Exception as e:
                    logger.debug(f"Error checking {ip_str}:{port}: {e}")

    # Создаем задачи для всех IP
    tasks = [check_ip(str(ip)) for ip in network.hosts()]
    await asyncio.gather(*tasks)

    return {
        "total_scanned": len(tasks),
        "found_yealink": len(found_phones),
        "newly_enrolled": len(enrolled_phones),
        "details": enrolled_phones,
        "debug": debug_info  # Добавили отладочную информацию
    }
