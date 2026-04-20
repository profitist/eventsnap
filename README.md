# EventSnap

Веб-сервис для совместных фотогалерей событий. Создай событие, пригласи людей через QR-код — они загружают фото напрямую в общую галерею.

## Стек

- **FastAPI** — REST API
- **PostgreSQL** + **SQLAlchemy 2.0** (async) — база данных
- **asyncpg** — драйвер БД
- **Alembic** — миграции
- **aioboto3** — S3-совместимое хранилище (AWS S3, MinIO, Yandex Cloud и др.)
- **pydantic-settings** — конфигурация через env

## Быстрый старт

```bash
# 1. Зависимости
pip install -r requirements.txt

# 2. Переменные окружения
cp .env .env  # заполни значения

# 3. Миграции
alembic upgrade head

# 4. Запуск
uvicorn src.main:app --reload
```

## Конфигурация

Все настройки через `.env` или переменные окружения:

```env
# База данных
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=eventsnap
DB_ECHO=false
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_PRE_PING=true

# Альтернатива: можно задать полный URL одной переменной.
# Если DATABASE_URL задан, отдельные DB_* поля для подключения игнорируются.
# DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@127.0.0.1:5432/eventsnap

# Безопасность
SECRET_KEY=your-secret-key  # обязательно

# S3 / Object Storage
S3_BUCKET_NAME=eventsnap
S3_REGION=us-east-1
S3_ENDPOINT_URL=          # оставь пустым для AWS, или укажи https://... для MinIO
S3_ACCESS_KEY_ID=         # обязательно
S3_SECRET_ACCESS_KEY=     # обязательно
S3_BASE_URL=              # базовый URL для публичных ссылок, обязательно
S3_PRESIGN_UPLOAD_TTL=900
S3_PRESIGN_DOWNLOAD_TTL=3600
```

`SECRET_KEY`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BASE_URL` — обязательные поля. Приложение не запустится без них.

Для подключения к PostgreSQL используется асинхронный драйвер `asyncpg`, поэтому URL базы должен быть `postgresql+asyncpg://...`. Если в `DATABASE_URL` указать обычный `postgresql://...`, приложение автоматически приведёт его к asyncpg-варианту.

## Docker

Для деплоя на VM можно использовать `docker-compose.yml`. Compose сам читает `.env`, поэтому переменные окружения не нужно передавать руками при каждом запуске.

```bash
# 1. Создать и заполнить окружение
cp .env .env

# 2. Если PostgreSQL установлен прямо на той же VM, оставь:
# DB_HOST=host.docker.internal
#
# Если PostgreSQL находится на другой машине, укажи её IP или DNS:
# DB_HOST=10.0.0.5

# 3. Собрать образ
docker compose build

# 4. Применить миграции
docker compose run --rm migrate

# 5. Запустить API
docker compose up -d api
```

Важно: внутри контейнера `127.0.0.1` — это сам контейнер, а не VM. Если PostgreSQL установлен на той же VM, `docker-compose.yml` добавляет `host.docker.internal`, но сам PostgreSQL должен слушать не только localhost и разрешать подключения с Docker bridge в `pg_hba.conf`.

API будет доступен на порту `APP_PORT` из `.env` или на `8000` по умолчанию.

Если таблицы уже были созданы вручную SQL-скриптом, вместо миграции отметь базу как актуальную:

```bash
docker compose run --rm migrate alembic stamp head
```

## Структура проекта

```
src/
├── main.py                  # точка входа FastAPI
├── config.py                # настройки (pydantic-settings)
├── db/                      # подключение к БД, сессия, зависимости
├── models/                  # SQLAlchemy модели
│   ├── user.py              # User, UserPasswordCredential, UserOAuthAccount
│   ├── event.py             # Event, EventParticipant
│   ├── gallery.py           # Gallery
│   └── photo.py             # Photo
├── repositories/            # слой доступа к данным
│   ├── base.py              # Generic BaseRepository[ModelT]
│   ├── user_repository.py
│   ├── event_repository.py
│   ├── gallery_repository.py
│   └── photo_repository.py
├── photos/                  # загрузка фото, лента, модерация
│   ├── router.py            # /events/{id}/photos..., /photos/{id}/approve|reject
│   ├── schemas.py           # Photo request/response DTO
│   └── service.py           # бизнес-логика фото и модерации
└── s3/                      # клиент для объектного хранилища
    ├── client.py            # S3Client, get_s3_client (FastAPI Depends)
    └── keys.py              # построители S3-ключей
```

## Флоу загрузки фото

1. Клиент запрашивает presigned URL: `POST /events/{event_id}/photos/upload-url`
2. API возвращает `upload_url`, `upload_method`, `upload_headers`, `s3_key`, `photo_id` и сохраняет запись `Photo`
3. Клиент загружает файл **напрямую на S3** (через API-сервер не проходит)
4. Клиент подтверждает загрузку: `POST /photos/{photo_id}/complete`
5. Фоновый воркер генерирует thumbnail и обновляет запись

## Документация

- [`docs/mvp.md`](docs/mvp.md) — функциональные требования MVP (дедлайн: 7 апреля 2026)
- [`docs/technical.md`](docs/technical.md) — архитектура, модели БД, детали реализации
- [`docs/api.md`](docs/api.md) — API-контракт эндпоинтов (статус: реализован/запланирован)
- [`docs/frontend-flows.md`](docs/frontend-flows.md) — пользовательские сценарии и последовательности API-вызовов для фронтенда
