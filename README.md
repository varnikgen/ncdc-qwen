## NCDC (Network Configuration & Device Control)

Система автопровижининга IP-телефонов Yealink: веб-админка, иерархические cfg-файлы, HTTPS, 802.1x, DSS-клавиши, AutoP push и журнал аудита.

Версия **0.2.0** закрывает дыры безопасности и ломающие баги 0.1.x. Подробности — в [FIXES.md](FIXES.md).

### Стек

* Backend: Python 3.11, FastAPI, SQLAlchemy, Uvicorn
* Frontend: Jinja2, HTMX, Bootstrap 5
* БД: SQLite (WAL + foreign_keys)
* Reverse proxy: Nginx
* Контейнеры: Podman / Docker Compose

### Быстрый старт

```bash
git clone <your-repo-url>
cd ncdc-qwen

cp .env.example .env
# Обязательно задайте NCDC_ADMIN_PASS, SECRET_KEY, PROVISION_PASS, ACTION_URI_TOKEN, PUBLIC_BASE_URL

mkdir -p data nginx/ssl
chmod 0777 data   # или chown 1000:1000 data  (контейнер работает от uid 1000)

# Самоподписанный сертификат для лаборатории:
sh scripts/gen-ssl.sh ncdc.example.com

podman-compose up --build -d
# или: docker compose up --build -d
```

Откройте `https://<PUBLIC_BASE_URL>` и войдите учётками `NCDC_ADMIN_USER` / `NCDC_ADMIN_PASS`.

Без заполненного `.env` приложение **не стартует** — это специально, чтобы не поднять прод с `admin/ChangeMe123!`.

### Первичная настройка телефонов

1. **Global Config** — проверьте URL провижининга, часовой пояс, Action URL (токен подставляется сам при первом старте).
2. **Model Config** — создайте модель (T46U и т.д.), прошивку, 802.1x.
3. **Account List** — SIP-аккаунты.
4. **Device List** — добавьте MAC вручную **или** включите `AUTO_ENROLL=true` и дождитесь первого запроса телефона.

На телефоне (или через DHCP option 66/43) задайте:

* Server URL: `https://ncdc.example.com/provision/`
* Username / password: значения `PROVISION_USER` / `PROVISION_PASS`

Без этих учёток cfg не отдаётся — SIP-пароли больше не торчат в открытую.

### Переменные окружения

См. `.env.example`. Критичные:

| Переменная | Назначение |
|---|---|
| `PUBLIC_BASE_URL` | URL, который телефоны используют для cfg и Action URL |
| `NCDC_ADMIN_PASS` | Пароль админки. Дефолты из git отклоняются |
| `PROVISION_PASS` | HTTP Basic для `/provision` |
| `ACTION_URI_TOKEN` | Секрет в `?token=` на `/actions` |
| `AUTO_ENROLL` | Создавать телефон при первом cfg / Action URL |
| `BOOT_OVERWRITE_MODE` | `1` — централизованные настройки перекрывают локальные |

### Безопасность (обязательный минимум)

* `/provision` закрыт HTTP Basic (`PROVISION_USER` / `PROVISION_PASS`).
* `/actions` принимает запросы только с верным `token`.
* Админка: Basic Auth + CSRF + lockout после 5 неверных попыток.
* `DEBUG=false` по умолчанию, SQL-echo выключен.
* Пароли SIP в формах не отображаются; пустое поле = оставить прежний.
* Контейнер запускается от пользователя `ncdc` (uid 1000).

### Структура

```text
ncdc-qwen/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── security.py
│   ├── middleware/          # admin auth, CSRF
│   ├── routers/
│   ├── services/
│   └── templates/
├── nginx/nginx.conf
├── scripts/gen-ssl.sh
├── .env.example
├── Dockerfile / Containerfile
└── podman-compose.yml
```

### Тесты

```bash
pip install -r requirements-dev.txt
pytest
```

### Резервное копирование

```bash
cp data/ncdc.db backups/ncdc_$(date +%Y%m%d).db
```

Файл БД содержит SIP-пароли — храните бэкапы как секрет.

### Лицензия

MIT. См. [LICENSE](LICENSE).
