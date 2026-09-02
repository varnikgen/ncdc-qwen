import httpx
import logging

logger = logging.getLogger("ncdc.push_service")

async def trigger_phone_autop(ip_address: str) -> bool:
    """
    Отправляет запрос на телефон для немедленного получения новых настроек.
    """
    if not ip_address:
        logger.warning("Невозможно отправить AutoP: IP-адрес телефона неизвестен.")
        return False

    url = f"http://{ip_address}/servlet?key=AutoP"
    
    try:
        # Таймаут 3 секунды, чтобы не блокировать воркеры при недоступности телефона
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                logger.info(f"✅ AutoP успешно отправлен на {ip_address}")
                return True
            else:
                logger.warning(f"⚠️ AutoP вернул статус {response.status_code} для {ip_address}")
                return False
    except httpx.RequestError as exc:
        logger.error(f"❌ Ошибка сети при отправке AutoP на {ip_address}: {exc}")
        return False