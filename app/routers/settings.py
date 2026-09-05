from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import json

from app.database import get_db
from app.models import GlobalConfig, AuditLog
from app.services.audit import log_action

router = APIRouter(prefix="/settings", tags=["settings"])

# Маппинг "человеческих" названий для параметров
PARAM_LABELS = {
    # Network
    "static.network.ip_address_mode": "IP Address Mode",
    "static.network.ipv6_enable": "Enable IPv6",
    "static.network.static_dns_enable": "Use Static DNS",
    "static.network.primary_dns": "Primary DNS",
    "static.network.secondary_dns": "Secondary DNS",
    "static.network.vlan.internet_port_enable": "Enable VLAN",
    "static.network.vlan.internet_port_vid": "VLAN ID",
    "static.network.vlan.internet_port_priority": "VLAN Priority (CoS)",
    
    # LDAP
    "ldap.enable": "Enable LDAP",
    "ldap.host": "LDAP Server",
    "ldap.base": "Base DN",
    "ldap.user": "LDAP User",
    "ldap.password": "LDAP Password",
    "ldap.name_attr": "Name Attributes",
    "ldap.numb_attr": "Number Attribute",
    "ldap.name_filter": "Name Filter",
    "ldap.number_filter": "Number Filter",
    "ldap.display_name": "Display Name Format",
    "ldap.call_in_lookup": "Enable Call-In Lookup",
    "ldap.customize_label": "LDAP Label",
    
    # Time & Date
    "local_time.time_zone": "Time Zone",
    "local_time.dhcp_time": "Use DHCP Time",
    "local_time.summer_time": "Enable Summer Time",
    "local_time.date_format": "Date Format",
    "local_time.time_zone_name": "Time Zone Name",
    
    # Auto Provision
    "static.auto_provision.server.url": "Provisioning Server URL",
    "static.auto_provision.power_on": "Auto Provision on Power On",
    "static.auto_provision.repeat.minutes": "Repeat Interval (minutes)",
    "static.auto_provision.custom.protect": "Protect Custom Settings",
    "static.auto_provision.weekly.enable": "Enable Weekly Provisioning",
    
    # Action URI
    "features.action_uri_limit_ip": "Action URI Limit IP",
    "features.action_uri.phone.enable": "Enable Phone Action URI",
    "features.action_uri.expansion_module.enable": "Enable Expansion Module Action URI",
    
    # Дополнительные
    "features.remote_phonebook.enable": "Enable Remote Phonebook",
    "features.dnd.allow": "Allow DND",
    "features.fwd.allow": "Allow Forward",
    "features.show_action_uri_option": "Show Action URI Option",
    "phone_setting.ring_type": "Ring Tone",
    "voice.handset.spk_vol": "Handset Speaker Volume",
    "voice.ring_vol": "Ring Volume",
    "directory.edit_default_input_method": "Directory Input Method",
    "action_url.show_msgbox": "Show Action URL Message Box",
}

# Значения для select-полей
SELECT_OPTIONS = {
    "static.network.ip_address_mode": {
        "0": "IPv4 Only",
        "1": "IPv6 Only",
        "2": "IPv4 & IPv6"
    },
    "local_time.date_format": {
        "0": "YYYY-MM-DD",
        "1": "DD-MM-YYYY",
        "2": "MM-DD-YYYY",
        "3": "DD/MM/YYYY",
        "4": "MM/DD/YYYY",
        "5": "YYYY/MM/DD"
    },
    "local_time.time_zone": {
        "-12": "UTC-12",
        "-11": "UTC-11",
        "-10": "UTC-10",
        "-9": "UTC-9",
        "-8": "UTC-8 (PST)",
        "-7": "UTC-7 (MST)",
        "-6": "UTC-6 (CST)",
        "-5": "UTC-5 (EST)",
        "-4": "UTC-4",
        "-3": "UTC-3",
        "-2": "UTC-2",
        "-1": "UTC-1",
        "0": "UTC+0 (GMT)",
        "+1": "UTC+1 (CET)",
        "+2": "UTC+2 (EET)",
        "+3": "UTC+3 (MSK)",
        "+4": "UTC+4",
        "+5": "UTC+5",
        "+6": "UTC+6",
        "+7": "UTC+7",
        "+8": "UTC+8",
        "+9": "UTC+9",
        "+10": "UTC+10 (VLAT)",
        "+11": "UTC+11",
        "+12": "UTC+12"
    },
}

# Группировка параметров по категориям
PARAM_GROUPS = {
    "Network": [
        "static.network.ip_address_mode",
        "static.network.ipv6_enable",
        "static.network.static_dns_enable",
        "static.network.primary_dns",
        "static.network.secondary_dns",
        "static.network.vlan.internet_port_enable",
        "static.network.vlan.internet_port_vid",
        "static.network.vlan.internet_port_priority",
    ],
    "LDAP": [
        "ldap.enable",
        "ldap.host",
        "ldap.base",
        "ldap.user",
        "ldap.password",
        "ldap.name_attr",
        "ldap.numb_attr",
        "ldap.name_filter",
        "ldap.number_filter",
        "ldap.display_name",
        "ldap.call_in_lookup",
        "ldap.customize_label",
    ],
    "Time & Date": [
        "local_time.time_zone",
        "local_time.dhcp_time",
        "local_time.summer_time",
        "local_time.date_format",
        "local_time.time_zone_name",
    ],
    "Auto Provision": [
        "static.auto_provision.server.url",
        "static.auto_provision.power_on",
        "static.auto_provision.repeat.minutes",
        "static.auto_provision.custom.protect",
        "static.auto_provision.weekly.enable",
    ],
    "Action URI": [
        "features.action_uri_limit_ip",
        "features.action_uri.phone.enable",
        "features.action_uri.expansion_module.enable",
    ],
    "Features": [
        "features.remote_phonebook.enable",
        "features.dnd.allow",
        "features.fwd.allow",
        "features.show_action_uri_option",
        "phone_setting.ring_type",
        "voice.handset.spk_vol",
        "voice.ring_vol",
        "directory.edit_default_input_method",
        "action_url.show_msgbox",
    ],
}

# Параметры, которые являются boolean (0/1)
BOOLEAN_PARAMS = {
    "static.network.ipv6_enable",
    "static.network.static_dns_enable",
    "static.network.vlan.internet_port_enable",
    "ldap.enable",
    "ldap.call_in_lookup",
    "local_time.dhcp_time",
    "local_time.summer_time",
    "static.auto_provision.power_on",
    "static.auto_provision.custom.protect",
    "static.auto_provision.weekly.enable",
    "features.action_uri.phone.enable",
    "features.action_uri.expansion_module.enable",
    "features.remote_phonebook.enable",
    "features.dnd.allow",
    "features.fwd.allow",
    "features.show_action_uri_option",
    "action_url.show_msgbox",
}


def normalize_value(param: str, value: str):
    """Приводит значение к правильному типу в зависимости от параметра"""
    if param in BOOLEAN_PARAMS:
        return 1 if value in ("1", "on", "true", "True") else 0
    
    # Целочисленные параметры
    int_params = {
        "static.network.vlan.internet_port_vid",
        "static.network.vlan.internet_port_priority",
        "static.auto_provision.repeat.minutes",
        "voice.handset.spk_vol",
        "voice.ring_vol",
    }
    if param in int_params:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    
    return value


@router.get("/global")
async def global_config(request: Request, db: Session = Depends(get_db)):
    """Страница редактирования глобальных настроек"""
    global_cfg = db.query(GlobalConfig).first()
    settings = global_cfg.settings if global_cfg and global_cfg.settings else {}
    
    # Группируем настройки по категориям
    grouped_settings = {}
    for group_name, params in PARAM_GROUPS.items():
        group_data = []
        for param in params:
            value = settings.get(param, "")
            group_data.append({
                "key": param,
                "label": PARAM_LABELS.get(param, param),
                "value": value,
                "type": "select" if param in SELECT_OPTIONS else ("boolean" if param in BOOLEAN_PARAMS else "text"),
                "options": SELECT_OPTIONS.get(param, {})
            })
        grouped_settings[group_name] = group_data
    
    # Параметры, которые не вошли ни в одну группу (Custom)
    known_params = set()
    for params in PARAM_GROUPS.values():
        known_params.update(params)
    
    custom_params = []
    for key, value in settings.items():
        if key not in known_params:
            custom_params.append({
                "key": key,
                "label": key,
                "value": value,
                "type": "text",
                "options": {}
            })
    
    return request.app.state.templates.TemplateResponse("settings/global.html", {
        "request": request,
        "grouped_settings": grouped_settings,
        "custom_params": custom_params
    })


@router.post("/global")
async def update_global_config(request: Request, db: Session = Depends(get_db)):
    """Сохранение глобальных настроек"""
    form = await request.form()
    
    global_cfg = db.query(GlobalConfig).first()
    if not global_cfg:
        global_cfg = GlobalConfig(settings={})
        db.add(global_cfg)
    
    settings = global_cfg.settings.copy() if global_cfg.settings else {}
    
    # Обрабатываем все поля формы
    changed_params = []
    for key, value in form.items():
        if key.startswith("param_"):
            param_name = key.replace("param_", "", 1)
            normalized = normalize_value(param_name, value)
            old_value = settings.get(param_name)
            if old_value != normalized:
                changed_params.append(f"{param_name}: {old_value} → {normalized}")
            settings[param_name] = normalized
    
    # Удаляем параметры, которые были очищены (пустая строка для не-boolean)
    for key, value in form.items():
        if key.startswith("delete_"):
            param_name = key.replace("delete_", "", 1)
            if param_name in settings:
                changed_params.append(f"{param_name}: {settings[param_name]} → [deleted]")
                del settings[param_name]
    
    global_cfg.settings = settings
    db.commit()
    db.refresh(global_cfg)
    
    log_action(
        db, "UPDATE_GLOBAL_CONFIG", "GlobalConfig", 
        global_cfg.id, "admin",
        f"Updated global config: {', '.join(changed_params) if changed_params else 'no changes'}"
    )
    
    return {"status": "success", "message": "Глобальные настройки успешно сохранены"}