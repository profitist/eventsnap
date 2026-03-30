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
cp .env.example .env  # заполни значения

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
DB_HOST=localhost
DB_NAME=eventsnap

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
2. API возвращает URL и сохраняет запись `Photo` со статусом `pending`
3. Клиент загружает файл **напрямую на S3** (через API-сервер не проходит)
4. Фоновый воркер генерирует thumbnail и обновляет запись

## Документация

- [`docs/mvp.md`](docs/mvp.md) — функциональные требования MVP (дедлайн: 7 апреля 2026)
- [`docs/technical.md`](docs/technical.md) — архитектура, модели БД, детали реализации
- [`docs/api.md`](docs/api.md) — API-контракт эндпоинтов (статус: реализован/запланирован)
- [`docs/frontend-flows.md`](docs/frontend-flows.md) — пользовательские сценарии и последовательности API-вызовов для фронтенда
