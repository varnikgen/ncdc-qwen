## NCDC (Network Configuration & Device Control)

Система автопровижининга IP-телефонов Yealink: веб-админка, иерархические cfg-файлы, HTTPS, 802.1x, DSS-клавиши, AutoP push и журнал аудита.

Версия **0.2.6**. Подробности — в [FIXES.md](FIXES.md).

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

Если `pip install` внутри образа падает с `Network is unreachable` / `Errno 101` —
у контейнера нет выхода на pypi.org (часто rootless Podman). Два варианта:

**A. Сеть хоста на время сборки**

```bash
podman build --network=host -t ncdc-qwen .
podman-compose up -d
```

В `podman-compose.yml` для `build` уже стоит `network: host`.

**B. Колёса с Windows (там pip у вас работает)**

На ПК:

```powershell
.\scripts\download-linux-wheels.ps1
```

Скопируйте папку `vendor\py311-linux\` на сервер в тот же путь репозитория.
Сборка больше не ходит в интернет:

```bash
podman-compose up --build -d
```

Не берите колёса из своего Windows-venv — они не подойдут Linux-образу.
Скрипт качает именно `manylinux` / CPython 3.11.

### Windows: имя уже смотрит на этот ПК

`ncdc-dev.bsmuk.ru` → `uk-khv-001-nv.bsmuk.ru` → **10.30.30.30**.
Если `ipconfig` показывает `10.30.30.30`, DNS правильный. Отказ в соединении —
потому что **Podman слушает порты внутри своей ВМ**, а не на Ethernet Windows.
Телефоны и браузер бьют в `10.30.30.30:80/443`, там пусто.

Не чините hosts. Запускайте без контейнеров (venv у вас уже ставится):

```powershell
# в .env:
# PUBLIC_BASE_URL=http://ncdc-dev.bsmuk.ru:8000

.\scripts\run-windows.ps1
```

Дальше:

* админка: http://10.30.30.30:8000/ или http://ncdc-dev.bsmuk.ru:8000/
* health: `curl.exe http://10.30.30.30:8000/health`
* брандмауэр: разрешить входящий TCP 8000

Порт 80 (тогда URL без `:8000`) — тот же скрипт `-Port 80` из PowerShell **администратора**.

Проверка, кто слушает:

```powershell
powershell -File .\scripts\where-is-ncdc.ps1
```

Логин: `NCDC_ADMIN_USER` / `NCDC_ADMIN_PASS` из `.env`.

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
