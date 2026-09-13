# Копия Containerfile для docker compose (ищет Dockerfile по умолчанию).
# Образ приложения. Не root: том ./data должен быть writable uid 1000.
FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --uid 1000 ncdc

COPY requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/app/static \
    && chown -R ncdc:ncdc /app

USER ncdc

ENV DATABASE_URL=sqlite:///./data/ncdc.db
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
