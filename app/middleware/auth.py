from fastapi import Request, status
from fastapi.responses import PlainTextResponse
import base64
import os

# .strip() удалит случайные пробелы или переносы строк из .env файла
ADMIN_USER = os.getenv("NCDC_ADMIN_USER", "admin").strip()
ADMIN_PASS = os.getenv("NCDC_ADMIN_PASS", "ChangeMe123!").strip()

# Пути, которые НЕ требуют авторизации
EXCLUDED_PATHS = [
    "/provision",
    "/health",
    "/actions",
    "/favicon.ico",  # Браузеры запрашивают его автоматически
    "/static",       # Если будут добавлены статические файлы
]

async def basic_auth_middleware(request: Request, call_next):
    path = request.url.path
    
    # 1. Исключаем определенные пути (используем any для чистоты кода)
    if any(path.startswith(excluded) for excluded in EXCLUDED_PATHS):
        return await call_next(request)
    
    # 2. Проверяем заголовок Authorization
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return PlainTextResponse(
            "Unauthorized",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic realm=\"NCDC Admin Panel\""},
        )

    try:
        # Разделяем схему и данные
        scheme, credentials = auth_header.split(None, 1)
        if scheme.lower() != "basic":
            return PlainTextResponse("Invalid auth scheme", status_code=400)
        
        # Декодируем base64
        decoded = base64.b64decode(credentials).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return PlainTextResponse("Invalid authorization header", status_code=400)

    # 3. Сравниваем (также используем strip() на случай опечаток при вводе)
    if username.strip() != ADMIN_USER or password.strip() != ADMIN_PASS:
        # Возвращаем Response напрямую, а не raise HTTPException!
        return PlainTextResponse(
            "Incorrect username or password",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": "Basic realm=\"NCDC Admin Panel\""},
        )

    # 4. Всё ок, пропускаем запрос
    return await call_next(request)