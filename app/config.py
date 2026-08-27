from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Приложение
    APP_NAME: str = "NCDC"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # База данных
    DATABASE_URL: str = "sqlite:///./data/ncdc.db"
    
    # Сервер
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Provisioning
    PROVISIONING_BASE_URL: str = "https://ncdc.bsmuk.ru/yealink/"
    
    # AutoP
    AUTOP_TIMEOUT: int = 3  # секунды
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()