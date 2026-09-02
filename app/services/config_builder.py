import json
from sqlalchemy.orm import Session
from app.models import Phone, PhoneModel, Account, GlobalConfig

def get_merged_config(db: Session, mac: str) -> dict:
    mac_clean = mac.replace(":", "").replace("-", "").upper()
    print(f"\n[DEBUG] === Начало сборки конфига для MAC: {mac_clean} ===")
    
    global_cfg = db.query(GlobalConfig).first()
    config = global_cfg.settings.copy() if global_cfg and global_cfg.settings else {}
    
    phone = db.query(Phone).filter(Phone.mac == mac_clean).first()
    if not phone:
        print(f"[DEBUG] Телефон не найден, создаем новый: {mac_clean}")
        phone = Phone(mac=mac_clean, status="offline", account_ids=[])
        db.add(phone)
        db.commit()
        db.refresh(phone)
    
    print(f"[DEBUG] Телефон найден. model_name={phone.model_name}")
    print(f"[DEBUG] Сырое значение account_ids из БД: {phone.account_ids} (тип: {type(phone.account_ids)})")
    print(f"[DEBUG] primary_account_id: {phone.primary_account_id}")

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
    
    if phone.custom_config:
        config.update(phone.custom_config)
    
    accounts_config = []
    primary_account = None
    
    # БЕЗОПАСНОЕ извлечение account_ids (защита от строки вместо списка)
    raw_account_ids = phone.account_ids
    if isinstance(raw_account_ids, str):
        try:
            account_ids = json.loads(raw_account_ids)
            print(f"[DEBUG] Преобразовали строку account_ids в список: {account_ids}")
        except json.JSONDecodeError:
            account_ids = []
            print(f"[DEBUG] Ошибка парсинга JSON, используем пустой список")
    else:
        account_ids = raw_account_ids or []
        print(f"[DEBUG] account_ids уже является списком или None: {account_ids}")

    if account_ids:
        for line_index, acc_id in enumerate(account_ids):
            print(f"[DEBUG] Ищем аккаунт с ID: {acc_id}")
            acc = db.query(Account).filter(Account.id == acc_id).first()
            if acc:
                print(f"[DEBUG] Аккаунт найден: {acc.name} (username: {acc.username})")
                accounts_config.append({
                    "line": line_index + 1,
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
            else:
                print(f"[DEBUG] Аккаунт с ID {acc_id} НЕ НАЙДЕН в БД!")
    else:
        print("[DEBUG] Список account_ids пуст!")

    config["accounts"] = accounts_config
    
    dss_keys = []
    if phone.override_dss_keys and phone.custom_dss_keys:
        dss_keys = phone.custom_dss_keys
    elif primary_account and primary_account.dss_keys:
        dss_keys = primary_account.dss_keys
        
    config["dss_keys"] = dss_keys or []
    config["mac"] = mac_clean
    config["model"] = phone.model_name or "unknown"
    
    print(f"[DEBUG] Итоговый список аккаунтов для рендеринга: {len(accounts_config)} шт.")
    print(f"[DEBUG] === Конец сборки конфига ===\n")
    
    return config