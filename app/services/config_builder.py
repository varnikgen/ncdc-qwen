"""Сборка контекста для Jinja-шаблонов провижининга.

Иерархия файлов Yealink (boot include) уже разделяет global/model/phone,
поэтому здесь словари НЕ сливаются в один flat-dict: иначе параметры
дублировались бы в нескольких cfg и телефон получал конфликты.
"""
import logging
from app.models import Phone, Account, PhoneModel, GlobalConfig
from app.services.linekeys import render_linekeys_block

logger = logging.getLogger("ncdc.config_builder")


def build_phone_config(db, mac: str) -> dict:
    """Контекст для phone.cfg.j2. ValueError, если MAC нет в БД."""
    mac_clean = mac.replace(":", "").replace("-", "").lower()
    logger.info("Building config for MAC %s", mac_clean.upper())

    phone = db.query(Phone).filter(Phone.mac.ilike(mac_clean)).first()
    if not phone:
        raise ValueError(f"Телефон с MAC {mac} не найден")

    global_cfg = db.query(GlobalConfig).first()
    global_settings = global_cfg.settings if global_cfg and global_cfg.settings else {}

    model = db.query(PhoneModel).filter(PhoneModel.name == phone.model_name).first()
    model_settings = model.default_config if model and model.default_config else {}
    phone_settings = phone.custom_config if phone.custom_config else {}

    final_config = {
        "global": global_settings,
        "model": model_settings,
        "phone": phone_settings,
        "phone_info": {
            "mac": phone.mac,
            "model": phone.model_name,
        },
    }

    # index в enumerate(start=1) = номер линии Yealink (account.N.*)
    accounts_data = []
    if phone.account_ids and isinstance(phone.account_ids, list):
        for idx, acc_id in enumerate(phone.account_ids, start=1):
            acc = db.query(Account).filter(Account.id == acc_id).first()
            if acc:
                accounts_data.append(
                    {
                        "index": idx,
                        "name": acc.name,
                        "username": acc.username,
                        "password": acc.password,
                        "sip_server": acc.sip_server,
                        "sip_port": acc.sip_port,
                        "transport": acc.transport,
                        "display_name": acc.display_name,
                    }
                )
    final_config["accounts"] = accounts_data

    # Индивидуальные DSS имеют приоритет над наследством с primary-аккаунта
    dss_keys = []
    if phone.override_dss_keys and phone.custom_dss_keys:
        dss_keys = sorted(phone.custom_dss_keys, key=lambda x: x.get("line", 0))
    elif phone.primary_account_id:
        primary_acc = db.query(Account).filter(Account.id == phone.primary_account_id).first()
        if primary_acc and primary_acc.dss_keys:
            dss_keys = sorted(primary_acc.dss_keys, key=lambda x: x.get("line", 0))
    final_config["dss_keys"] = dss_keys

    max_keys = model.max_dss_keys if model and model.max_dss_keys else 27
    final_config["linekeys_block"] = render_linekeys_block(dss_keys, max_keys)

    return final_config


def build_model_config(model_obj, identifier: str) -> dict:
    """Контекст для model.cfg.j2. Неизвестная модель → пустые поля, не 404:
    трубка всё равно запросит $PN.cfg, даже если линейки нет в NCDC.
    """
    config = {
        "model_name": identifier.upper(),
        "model_firmware_url": None,
        "model_802_1x_enable": False,
        "model_802_1x_identity": "",
        "model_802_1x_mode": 0,
        "model_802_1x_md5_password": "",
        "model_802_1x_root_cert_url": "",
        "model_802_1x_client_cert_url": "",
        "model_802_1x_upload_mode": 0,
        "model_default_config": {},
    }
    if model_obj:
        config.update(
            {
                "model_firmware_url": model_obj.firmware_url,
                "model_802_1x_enable": bool(model_obj.ieee802_1x_enable),
                "model_802_1x_identity": model_obj.ieee802_1x_identity,
                "model_802_1x_mode": model_obj.ieee802_1x_mode,
                "model_802_1x_md5_password": model_obj.ieee802_1x_md5_password or "",
                "model_802_1x_root_cert_url": model_obj.ieee802_1x_root_cert_url,
                "model_802_1x_client_cert_url": model_obj.ieee802_1x_client_cert_url,
                "model_802_1x_upload_mode": model_obj.ieee802_1x_upload_mode,
                "model_default_config": model_obj.default_config or {},
            }
        )
    return config
