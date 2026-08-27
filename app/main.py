from fastapi import FastAPI
from app.database import engine, Base
from app.config import settings
from app.routers import provisioning, actions  # <-- ДОБАВИТЬ actions

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Yealink Auto-Provisioning Service"
)

app.include_router(provisioning.router)
app.include_router(actions.router)  # <-- ДОБАВИТЬ ЭТО

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.APP_NAME}"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}