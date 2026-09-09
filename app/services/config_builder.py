import json
import logging
from app.models import Phone, Account, PhoneModel, GlobalConfig

logger = logging.getLogger("ncdc.config_builder")

def build_phone_config(db, mac: str) -> dict:
    mac_clean = mac.replace(":", "").lower()
    logger.info(f"=== Начало сборки конфига для MAC: {mac_clean.upper()} ===")
    
    # 1. Загружаем телефон
    phone = db.query(Phone).filter(Phone.mac.ilike(mac_clean)).first()
    if not phone:
        raise ValueError(f"Телефон с MAC {mac} не найден")
    
    # 2. Загружаем глобальные настройки
    global_cfg = db.query(GlobalConfig).first()
    global_settings = global_cfg.settings if global_cfg and global_cfg.settings else {}
    
    # 3. Загружаем настройки модели
    model = db.query(PhoneModel).filter(PhoneModel.name == phone.model_name).first()
    model_settings = model.default_config if model and model.default_config else {}
    
    # 4. Загружаем настройки телефона
    phone_settings = phone.custom_config if phone.custom_config else {}
    
    # 5. СТРУКТУРИРОВАННЫЙ СЛОВАРЬ (БЕЗ СЛИЯНИЯ!)
    final_config = {
        "global": global_settings,
        "model": model_settings,
        "phone": phone_settings,
    }
    
    # 6. Добавляем специфичные сущности (ваш существующий код)
    final_config["phone_info"] = {
        "mac": phone.mac,
        "model": phone.model_name
    }
    
    # Обработка аккаунтов
    accounts_data = []
    if phone.account_ids and isinstance(phone.account_ids, list):
        for idx, acc_id in enumerate(phone.account_ids, start=1):
            acc = db.query(Account).filter(Account.id == acc_id).first()
            if acc:
                accounts_data.append({
                    "index": idx,
                    "name": acc.name,
                    "username": acc.username,
                    "password": acc.password,
                    "sip_server": acc.sip_server,
                    "sip_port": acc.sip_port,
                    "transport": acc.transport,
                    "display_name": acc.display_name
                })
    final_config["accounts"] = accounts_data
    
    # Обработка DSS-клавиш (уже отсортированных)
    dss_keys = []
    if phone.override_dss_keys and phone.custom_dss_keys:
        dss_keys = sorted(phone.custom_dss_keys, key=lambda x: x.get('line', 0))
    elif phone.primary_account_id:
        primary_acc = db.query(Account).filter(Account.id == phone.primary_account_id).first()
        if primary_acc and primary_acc.dss_keys:
            dss_keys = sorted(primary_acc.dss_keys, key=lambda x: x.get('line', 0))
            
    final_config["dss_keys"] = dss_keys
    
    logger.info(f"=== Конец сборки конфига. Всего параметров: {len(final_config)} ===")
    return final_config