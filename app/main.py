from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from app.config import settings
from app.routers import provisioning, actions, phones, accounts

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

# Подключаем роутеры
app.include_router(provisioning.router)
app.include_router(actions.router)
app.include_router(phones.router)
app.include_router(accounts.router)

@app.get("/")
async def dashboard(request: Request):
    # Заглушка для Dashboard, пока используем простую статистику
    from app.models import Phone
    from app.database import get_db
    
    # Простой способ получить сессию для дашборда
    from sqlalchemy.orm import Session
    db = next(get_db())
    total = db.query(Phone).count()
    online = db.query(Phone).filter(Phone.status == "online").count()
    offline = db.query(Phone).filter(Phone.status.in_(["offline", "unregistered"])).count()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "stats": {
            "phones_count": total,
            "online_count": online,
            "offline_count": offline
        }
    })

@app.get("/health")
async def health_check():
    return {"status": "healthy"}