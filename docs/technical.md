# EventSnap — Техническая часть

## Стек

| Слой | Технология |
|---|---|
| API | FastAPI 0.135 |
| БД | PostgreSQL + SQLAlchemy 2.0 (async) |
| Драйвер БД | asyncpg |
| Миграции | Alembic |
| Валидация | Pydantic v2 + pydantic-settings |
| Хранилище файлов | S3-совместимое (AWS S3 / MinIO / Yandex Cloud и др.) |
| S3-клиент | aioboto3 13.3 (async wrapper над boto3) |
| Линтер | Ruff |
| Платформа | Web (без мобильного приложения) |

## Архитектура

```
src/
├── main.py                  # точка входа FastAPI
├── config.py                # настройки через pydantic-settings
├── db/                      # подключение к БД, сессия
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
└── s3/                      # клиент для работы с файловым хранилищем
    ├── __init__.py          # реэкспорт публичного API модуля
    ├── client.py            # S3Client, S3Error, get_s3_client (FastAPI Depends)
    └── keys.py              # построители S3-ключей для всех типов объектов
```

## Модели БД

### users
Зарегистрированные пользователи. Роли: `admin`, `organizer`, `guest`.
Аутентификация: email+password и/или OAuth (Google, Apple).

### user_password_credentials
Bcrypt-хеш пароля. Отдельная таблица — OAuth-пользователи не имеют строки здесь.

### user_oauth_accounts
OAuth-аккаунты. Один пользователь может иметь несколько провайдеров одновременно.

### events
Мероприятие. Содержит: название, описание, геолокацию, временные рамки, обложку,
QR-токен для входа, статус (`draft → active → finished → archived`).

### event_participants
Связь пользователь ↔ событие. Создаётся при сканировании QR.
Роль внутри события: `organizer` (co-host) или `attendee`.

### galleries
Галерея фотографий. Связь 1:1 с Event.
Флаг `moderation_enabled` — если `false`, фото публикуются без проверки.

### photos
Фотография. Хранит S3-ключи оригинала и thumbnail.
Модерация: `pending → approved / rejected`.

## Паттерн репозиториев

Репозитории не делают `commit()` — это ответственность сервисного слоя.
После записи вызывается `flush()` чтобы получить DB-generated значения.

## Хранилище файлов (S3)

В БД хранится только S3-ключ, base URL берётся из конфига (`S3_BASE_URL`).

### Структура ключей

| Тип объекта | Ключ |
|---|---|
| Оригинал фото | `photos/{event_id_hex}/{photo_id_hex}/original.{ext}` |
| Thumbnail фото | `photos/{event_id_hex}/{photo_id_hex}/thumb_400.{ext}` |
| Обложка события | `covers/{event_id_hex}/cover.{ext}` |
| Аватар пользователя | `avatars/{user_id_hex}/avatar.{ext}` |

UUID-ы хранятся в ключах без дефисов (hex), расширение определяется по MIME-типу.
Все построители ключей сосредоточены в `src/s3/keys.py`.

### Клиент (`S3Client`)

Обёртка над aioboto3 в `src/s3/client.py`. Поддерживает:
- `generate_presigned_upload_url` — presigned PUT URL для прямой загрузки с клиента
- `generate_presigned_download_url` — presigned GET URL для приватных объектов
- `upload_bytes` — серверная загрузка (для небольших объектов, фоновых воркеров)
- `delete_object` / `delete_objects` — удаление одного или пакета объектов
- `object_exists` — проверка существования через `head_object`
- `copy_object` — серверное копирование в пределах бакета
- `build_public_url` — сборка URL через CDN/базовый адрес без I/O

Синглтон-инстанс получается через FastAPI-зависимость `get_s3_client()`.

### Переменные окружения S3

| Переменная | Описание | По умолчанию |
|---|---|---|
| `S3_BUCKET_NAME` | Имя бакета | `eventsnap` |
| `S3_REGION` | Регион | `us-east-1` |
| `S3_ENDPOINT_URL` | Кастомный endpoint (MinIO и т.д.) | `None` (AWS) |
| `S3_ACCESS_KEY_ID` | Ключ доступа | — |
| `S3_SECRET_ACCESS_KEY` | Секретный ключ | — |
| `S3_BASE_URL` | Базовый URL для публичных ссылок | — |
| `S3_PRESIGN_UPLOAD_TTL` | TTL presigned upload URL (сек) | `900` |
| `S3_PRESIGN_DOWNLOAD_TTL` | TTL presigned download URL (сек) | `3600` |

### Рекомендуемый флоу загрузки фото

1. Клиент запрашивает presigned upload URL у API (`POST /photos/upload-url`).
2. API генерирует S3-ключ через `keys.photo_original_key(...)` и вызывает
   `S3Client.generate_presigned_upload_url(key, content_type)`.
3. API сохраняет `Photo` в БД со статусом `pending` и возвращает URL клиенту.
4. Клиент делает `PUT` напрямую на S3 (данные не проходят через API-сервер).
5. Фоновый воркер генерирует thumbnail и обновляет `Photo.thumbnail_s3_key`
   через `PhotoRepository.set_thumbnail_key(...)`.

Thumbnail (~400px) генерируется фоновым воркером после загрузки.

## Аутентификация

Два способа (оба поддерживаются одновременно):
- Email + password (bcrypt)
- OAuth 2.0: Google, Apple

## Важные замечания

- `add_participant` имеет TOCTOU race condition — ловить `IntegrityError` на сервисном уровне
- Soft delete через `deleted_at` на `users`, `events`, `galleries`, `photos`
- Soft delete галереи не каскадится на фото — сервис должен удалять явно