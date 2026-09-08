from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# 1. Импортируем настройки приложения
from app.config import settings

# 2. Импортируем роутеры (используем псевдоним 'as' для роутера настроек, чтобы избежать конфликта)
from app.routers import provisioning, actions, phones, accounts, settings as settings_router, models as models_router, audit as audit_router

from app.database import engine, Base

# Импортируем задачу очистки
from app.services.audit_cleanup import background_tasks
import asyncio

# Импортируем middleware
from app.middleware.auth import basic_auth_middleware

# Создаем таблицы в БД при старте
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Yealink Auto-Provisioning Service"
)

# Инициализируем шаблонизатор Jinja2 и сохраняем его в state приложения
templates = Jinja2Templates(directory="app/templates")
app.state.templates = templates

# Подключаем middleware
app.middleware("http")(basic_auth_middleware)

# Подключаем роутеры (обратите внимание на settings_router)
app.include_router(provisioning.router)
app.include_router(actions.router)
app.include_router(phones.router)
app.include_router(accounts.router)
app.include_router(settings_router.router)
app.include_router(models_router.router)
app.include_router(audit_router.router)


@app.on_event("startup")
async def startup_event():
    # Запускаем задачу очистки в фоне, не блокируя основной сервер
    asyncio.create_task(background_tasks())

@app.get("/")
async def dashboard(request: Request):
    from app.models import Phone
    from app.database import get_db
    
    db = next(get_db())
    
    # Корректный подсчет по реальным статусам
    total = db.query(Phone).count()
    online = db.query(Phone).filter(Phone.status == "online").count()
    dnd = db.query(Phone).filter(Phone.status == "dnd").count()
    offline = db.query(Phone).filter(Phone.status == "offline").count()
    unregistered = db.query(Phone).filter(Phone.status == "unregistered").count()
    
    return request.app.state.templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "stats": {
            "total": total,
            "online": online,
            "dnd": dnd,
            "offline": offline,
            "unregistered": unregistered
        }
    })

@app.get("/health")
async def health_check():
    return {"status": "healthy"}