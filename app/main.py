from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import jinja2
from pathlib import Path

from app.database import engine, Base
from app.config import settings
from app.routers import provisioning, actions, phones

# Создаём таблицы при старте (если их нет)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Yealink Auto-Provisioning Service"
)

# ==============================================================================
# Явная инициализация Jinja2 для обхода багов совместимости Starlette + Python 3.14
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
loader = jinja2.FileSystemLoader(str(BASE_DIR / "templates"))
jinja_env = jinja2.Environment(
    loader=loader,
    autoescape=True,
    auto_reload=True
)

# Подключаем роутеры
app.include_router(provisioning.router)
app.include_router(actions.router)
app.include_router(phones.router)

@app.get("/")
async def dashboard(request: Request):
    """Главная страница (Dashboard)"""
    stats = {
        "phones_count": 0,
        "online_count": 0,
        "offline_count": 0
    }
    # Прямой рендеринг шаблона без обёртки Starlette
    template = jinja_env.get_template("dashboard.html")
    html_content = template.render(request=request, stats=stats)
    return HTMLResponse(content=html_content)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}