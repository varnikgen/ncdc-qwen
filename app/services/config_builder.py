from sqlalchemy.orm import Session
from app.models import Phone, PhoneModel, Account, GlobalConfig

def get_merged_config(db: Session, mac: str) -> dict:
    """Собирает конфигурацию для телефона по MAC-адресу."""
    mac_clean = mac.replace(":", "").replace("-", "").upper()
    
    # 1. Глобальные настройки
    global_cfg = db.query(GlobalConfig).first()
    # Если глобального конфига нет, создаем пустой, чтобы не ломать рендеринг
    config = global_cfg.settings.copy() if global_cfg and global_cfg.settings else {}
    
    # 2. Телефон (авто-регистрация, если нет в БД)
    phone = db.query(Phone).filter(Phone.mac == mac_clean).first()
    if not phone:
        phone = Phone(mac=mac_clean, status="offline", account_ids=[])
        db.add(phone)
        db.commit()
        db.refresh(phone)
    
    # 3. Настройки модели
    if phone.model_name:
        model = db.query(PhoneModel).filter(PhoneModel.name == phone.model_name).first()
        if model:
            if model.default_config:
                config.update(model.default_config)
            config["model_firmware_url"] = model.firmware_url
            config["model_802_1x_enable"] = model.ieee802_1x_enable
            config["model_802_1x_identity"] = model.ieee802_1x_identity
            config["model_802_1x_mode"] = model.ieee802_1x_mode
            config["model_802_1x_root_cert_url"] = model.ieee802_1x_root_cert_url
            config["model_802_1x_client_cert_url"] = model.ieee802_1x_client_cert_url
    
    # 4. Индивидуальные настройки телефона
    if phone.custom_config:
        config.update(phone.custom_config)
    
    # 5. Сборка АККАУНТОВ
    accounts_config = []
    primary_account = None
    
    # Защита от None в JSON поле
    account_ids = phone.account_ids or []
    
    if account_ids:
        for line_index, acc_id in enumerate(account_ids):
            line_number = line_index + 1
            acc = db.query(Account).filter(Account.id == acc_id).first()
            if acc:
                accounts_config.append({
                    "line": line_number,
                    "label": acc.name,
                    "display_name": acc.display_name,
                    "auth_id": acc.username,
                    "user_id": acc.username,
                    "password": acc.password,
                    "server_address": acc.sip_server,
                    "sip_port": acc.sip_port,
                    "transport": acc.transport,
                    "register_expires": 3600,
                })
                if primary_account is None or acc.id == phone.primary_account_id:
                    primary_account = acc

    config["accounts"] = accounts_config
    
    # 6. Логика DSS-клавиш
    dss_keys = []
    if phone.override_dss_keys and phone.custom_dss_keys:
        dss_keys = phone.custom_dss_keys
    elif primary_account and primary_account.dss_keys:
        dss_keys = primary_account.dss_keys
        
    config["dss_keys"] = dss_keys or []
    config["mac"] = mac_clean
    config["model"] = phone.model_name or "unknown"
    
    return config