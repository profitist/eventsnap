# EventSnap — Техническая часть

Смежные документы:
- API-контракт: `docs/api.md`
- Frontend user flows: `docs/frontend-flows.md`

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
├── auth/                    # аутентификация
│   ├── router.py            # POST /auth/register, /login, /refresh, GET /me
│   ├── schemas.py           # Pydantic v2 request/response схемы
│   ├── service.py           # бизнес-логика: register, login, refresh
│   ├── passwords.py         # bcrypt hash/verify
│   ├── jwt.py               # JWT encode/decode, пара access + refresh
│   └── dependencies.py      # get_current_user (FastAPI Depends)
├── users/                   # профиль пользователя
│   ├── router.py            # PATCH /users/me, avatar upload-url/complete
│   ├── schemas.py           # UserUpdate, Avatar request/response схемы
│   └── service.py           # UserProfileService: update profile, avatar upload
├── events/                  # события
│   ├── router.py            # /events CRUD + /events/join + participants + gallery + cover
│   ├── schemas.py           # Event/Gallery/Cover/Participants request/response схемы
│   └── service.py           # EventService: CRUD, QR-join, participants, gallery, cover
├── photos/                  # фото и модерация
│   ├── router.py            # /events/{id}/photos..., /photos/{id}/approve|reject
│   ├── schemas.py           # Photo request/response схемы
│   └── service.py           # PhotoService: upload-url, feed, delete, moderation
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

1. Клиент запрашивает presigned upload URL у API (`POST /events/{event_id}/photos/upload-url`).
2. API генерирует S3-ключ через `keys.photo_original_key(...)` и вызывает
   `S3Client.generate_presigned_upload_url(key, content_type)`.
3. API сохраняет `Photo` в БД:
   - `pending`, если `gallery.moderation_enabled=true`
   - `approved`, если `gallery.moderation_enabled=false`
   и возвращает URL клиенту.
4. Клиент делает `PUT` напрямую на S3 (данные не проходят через API-сервер), используя метод и заголовки из ответа API.
5. Клиент вызывает `POST /photos/{photo_id}/complete`, API проверяет объект через `head_object`.
6. Фоновый воркер генерирует thumbnail и обновляет `Photo.thumbnail_s3_key`
   через `PhotoRepository.set_thumbnail_key(...)`.

Thumbnail (~400px) генерируется фоновым воркером после загрузки.

## Аутентификация

Два способа (оба поддерживаются одновременно):
- Email + password (bcrypt)
- OAuth 2.0: Google, Apple

Полный и актуальный список API-эндпоинтов см. в `docs/api.md`.

### Эндпоинты

| Метод | Путь | Описание | Auth |
|---|---|---|---|
| POST | `/auth/register` | Регистрация (email + пароль) | - |
| POST | `/auth/login` | Вход | - |
| POST | `/auth/refresh` | Обновление токенов | - |
| GET | `/auth/me` | Текущий пользователь | Bearer |

### JWT-токены

- **Access token** — `HS256`, TTL по умолчанию 30 минут
- **Refresh token** — `HS256`, TTL по умолчанию 7 дней
- Оба подписаны `SECRET_KEY`
- Payload: `{"sub": "<user_id>", "type": "access|refresh", "iat": ..., "exp": ...}`

### Переменные окружения

| Переменная | Описание | По умолчанию |
|---|---|---|
| `SECRET_KEY` | Ключ подписи JWT | обязательно |
| `JWT_ALGORITHM` | Алгоритм | `HS256` |
| `ACCESS_TOKEN_TTL_MINUTES` | TTL access token (мин) | `30` |
| `REFRESH_TOKEN_TTL_DAYS` | TTL refresh token (дни) | `7` |

### Защита роутов

```python
from src.auth.dependencies import get_current_user

@router.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    ...
```

### Заметки
- Email нормализуется в lowercase перед сохранением и поиском
- Login защищён от timing attacks: bcrypt выполняется даже при отсутствии пользователя
- Token blacklist / revocation отсутствует — для MVP достаточно TTL

## Профиль пользователя

Полный и актуальный список API-эндпоинтов см. в `docs/api.md`.

### Эндпоинты

| Метод | Путь | Описание | Auth |
|---|---|---|---|
| PATCH | `/users/me` | Обновить профиль (`display_name`) | Bearer |
| POST | `/users/me/avatar/upload-url` | Presigned URL для загрузки аватара | Bearer |
| POST | `/users/me/avatar/complete` | Подтвердить загрузку и сохранить `avatar_s3_key` | Bearer |

### Бизнес-логика

- `PATCH /users/me` принимает частичное обновление (только переданные поля)
- Загрузка аватара — двухшаговый процесс: получить URL → загрузить в S3 → подтвердить
- `complete` проверяет существование объекта в S3 через `head_object`
- S3-ключ аватара: `avatars/{user_id_hex}/avatar.{ext}` — перезаписывается при повторной загрузке

## События, QR и галерея

Полный и актуальный список API-эндпоинтов см. в `docs/api.md`.

### Эндпоинты

| Метод | Путь | Описание | Auth |
|---|---|---|---|
| POST | `/events` | Создать событие | Bearer |
| GET | `/events` | Список событий пользователя | Bearer |
| POST | `/events/join` | Вступить в событие по QR токену | Bearer |
| GET | `/events/{id}` | Получить событие (только участник) | Bearer |
| PATCH | `/events/{id}` | Обновить событие (организатор) | Bearer |
| DELETE | `/events/{id}` | Soft delete (организатор) | Bearer |
| GET | `/events/{id}/join-link` | Получить данные для QR-ссылки | Bearer (organizer) |
| GET | `/events/{id}/participants` | Список участников события | Bearer (participant) |
| GET | `/events/{id}/gallery` | Получить настройки галереи | Bearer (participant) |
| PATCH | `/events/{id}/gallery` | Обновить `moderation_enabled` | Bearer (organizer) |
| POST | `/events/{id}/cover/upload-url` | Presigned URL для обложки | Bearer (organizer) |
| POST | `/events/{id}/cover/complete` | Подтвердить загрузку обложки | Bearer (organizer) |

### Бизнес-логика

- Создание события автоматически создаёт Gallery (1:1) и добавляет создателя как `EventParticipant(role="organizer")`
- `GET /events?role=organizer|participant|all` — фильтрация по связи пользователя с событием
- `GET /events/{id}` и `GET /events/{id}/gallery` доступны только участникам события
- `POST /events/join` идемпотентен: повторный join не создаёт дубликаты
- Update/delete доступны только организатору (`event.organizer_id == user.id`), иначе 403
- Координаты и даты валидируются на уровне Pydantic (оба или ничего, `ends_at > starts_at`)
- Загрузка обложки — двухшаговый процесс (аналогично аватару): presigned URL → upload → complete
- `complete` проверяет наличие файла в S3 через `head_object`, затем сохраняет `cover_s3_key`

## Фото и модерация

Полный и актуальный список API-эндпоинтов см. в `docs/api.md`.

### Эндпоинты

| Метод | Путь | Описание | Auth |
|---|---|---|---|
| POST | `/events/{id}/photos/upload-url` | Создать `Photo`, выдать presigned upload URL | Bearer (participant) |
| POST | `/photos/{id}/complete` | Проверить, что файл загружен в S3 | Bearer |
| GET | `/events/{id}/photos` | Лента одобренных фото | Bearer (participant) |
| DELETE | `/photos/{id}` | Soft delete фото (uploader или organizer) | Bearer |
| GET | `/events/{id}/photos/pending` | Очередь модерации | Bearer (organizer) |
| GET | `/events/{id}/photos/pending/count` | Счётчик очереди модерации | Bearer (organizer) |
| POST | `/photos/{id}/approve` | Одобрить фото | Bearer (organizer) |
| POST | `/photos/{id}/reject` | Отклонить фото с комментарием | Bearer (organizer) |

## Важные замечания

- `add_participant` имеет TOCTOU race condition — ловить `IntegrityError` на сервисном уровне
- Soft delete через `deleted_at` на `users`, `events`, `galleries`, `photos`
- Soft delete галереи не каскадится на фото — сервис должен удалять явно
