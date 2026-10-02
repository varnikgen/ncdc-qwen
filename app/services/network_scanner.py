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

    # Ограничиваем одновременные запросы, чтобы не перегружать сеть и приложение
    semaphore = asyncio.Semaphore(50)

    async with httpx.AsyncClient(timeout=2.0, verify=False) as client:
        async def check_ip(ip_str: str):
            async with semaphore:
                try:
                    # 1. Проверяем корневую страницу. Yealink обычно отдает 401 с realm="Yealink"
                    response = await client.get(f"http://{ip_str}/")
                    www_auth = response.headers.get("www-authenticate", "").lower()
                    
                    if response.status_code == 401 and "yealink" in www_auth:
                        mac = "UNKNOWN"
                        
                        # 2. Пытаемся авторизоваться, чтобы получить MAC-адрес со страницы статуса
                        try:
                            auth_resp = await client.get(
                                f"http://{ip_str}/cgi-bin/ConfigManApp.com", 
                                auth=(username, password),
                                timeout=2.0
                            )
                            if auth_resp.status_code == 200:
                                # Ищем MAC-адрес в HTML (формат XX:XX:XX:XX:XX:XX или XX-XX-XX-XX-XX-XX)
                                match = re.search(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', auth_resp.text)
                                if match:
                                    mac = normalize_mac(match.group(0))
                        except Exception:
                            pass # Не смогли авторизоваться, но телефон все равно Yealink

                        found_phones.append({"ip": ip_str, "mac": mac})
                        
                        # 3. Если MAC известен, добавляем телефон в базу
                        if mac != "UNKNOWN":
                            existing = db.query(Phone).filter(Phone.mac.ilike(mac)).first()
                            if not existing:
                                new_phone = Phone(
                                    mac=mac, 
                                    ip_address=ip_str, 
                                    status="unregistered", 
                                    model_name="Unknown" # Модель определится при первом запросе конфига
                                )
                                db.add(new_phone)
                                db.commit()
                                db.refresh(new_phone)
                                enrolled_phones.append({"ip": ip_str, "mac": mac, "id": new_phone.id})
                                log_action(db, "NETWORK_SCAN_ENROLL", "Phone", new_phone.id, admin_user, f"Enrolled via network scan: {mac}")
                                
                except Exception:
                    pass # Игнорируем таймауты, закрытые порты и т.д.

        # Создаем задачи для всех IP в подсети
        tasks = [check_ip(str(ip)) for ip in network.hosts()]
        await asyncio.gather(*tasks)

    return {
        "total_scanned": len(tasks),
        "found_yealink": len(found_phones),
        "newly_enrolled": len(enrolled_phones),
        "details": enrolled_phones
    }
