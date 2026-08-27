from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class PhoneModel(Base):
    """Модель телефона (T46U, T31G, T48U и т.д.)"""
    __tablename__ = "phone_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)  # "T46U", "T31G"
    
    # Ограничения модели
    max_dss_keys = Column(Integer, default=27)
    max_accounts = Column(Integer, default=16)
    
    # Прошивка
    firmware_url = Column(String, nullable=True)  # "tftp://10.30.30.30/108.86.14.10.rom"
    
    # 802.1x авторизация
    ieee802_1x_enable = Column(Boolean, default=False)
    ieee802_1x_identity = Column(String, default="yealink")
    ieee802_1x_mode = Column(Integer, default=2)  # 0-EAP-TLS, 1-EAP-SIM, 2-EAP-MD5
    ieee802_1x_root_cert_url = Column(String, nullable=True)
    ieee802_1x_client_cert_url = Column(String, nullable=True)
    ieee802_1x_upload_mode = Column(Integer, default=0)
    
    # Дополнительные параметры модели (JSON)
    default_config = Column(JSON, default=dict)
    
    # Связи
    phones = relationship("Phone", back_populates="model")

class Account(Base):
    """SIP-аккаунт (самостоятельный объект)"""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)  # "Офис 205", "VarfolomeevNG"
    sip_server = Column(String, nullable=False)
    sip_port = Column(Integer, default=5060)
    transport = Column(String, default="udp")  # udp, tcp, tls
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    display_name = Column(String)
    
    # DSS-клавиши по умолчанию для этого аккаунта
    # Формат: [{"line": 1, "type": 16, "value": "206", "extension": "206", "label": "Иванов"}]
    dss_keys = Column(JSON, default=list)
    
    # Связи
    phones = relationship("Phone", back_populates="primary_account")

class Phone(Base):
    """Телефон (устройство)"""
    __tablename__ = "phones"
    
    id = Column(Integer, primary_key=True, index=True)
    mac = Column(String(12), unique=True, index=True, nullable=False)  # "001565C18725"
    model_name = Column(String, ForeignKey("phone_models.name"), nullable=True)
    
    # Список ID аккаунтов (порядок = номер линии: index 0 → account 1)
    account_ids = Column(JSON, default=list)
    
    # Первичный аккаунт (для наследования DSS-клавиш)
    primary_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    
    # Сеть и статус
    ip_address = Column(String, nullable=True)
    status = Column(String, default="offline")  # online, offline, dnd, unregistered
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    # DSS override
    override_dss_keys = Column(Boolean, default=False)
    custom_dss_keys = Column(JSON, nullable=True)
    
    # Индивидуальные настройки телефона (JSON)
    custom_config = Column(JSON, default=dict)
    
    # Связи
    model = relationship("PhoneModel", back_populates="phones")
    primary_account = relationship("Account", back_populates="phones", foreign_keys=[primary_account_id])

class GlobalConfig(Base):
    """Глобальная конфигурация (y000000000000.cfg)"""
    __tablename__ = "global_config"
    
    id = Column(Integer, primary_key=True, index=True)
    settings = Column(JSON, default=dict)

class AuditLog(Base):
    """Журнал аудита"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    action = Column(String, nullable=False)  # "UPDATE_PHONE", "CREATE_ACCOUNT"
    entity_type = Column(String, nullable=False)  # "Phone", "Account", "GlobalConfig"
    entity_id = Column(Integer)
    user = Column(String, default="system")
    details = Column(Text)  # JSON-строка с изменениями