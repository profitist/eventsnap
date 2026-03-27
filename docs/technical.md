# EventSnap — Техническая часть

## Стек

| Слой | Технология |
|---|---|
| API | FastAPI 0.135 |
| БД | PostgreSQL + SQLAlchemy 2.0 (async) |
| Драйвер БД | asyncpg |
| Миграции | Alembic |
| Валидация | Pydantic v2 |
| Хранилище файлов | S3-совместимое (конкретный провайдер TBD) |
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

В БД хранится только S3-ключ, base URL берётся из конфига.
Пример структуры ключей:
```
photos/{event_id}/{photo_id}/original.jpg
photos/{event_id}/{photo_id}/thumb_400.jpg
```
Thumbnail (~400px) генерируется фоновым воркером после загрузки.

## Аутентификация

Два способа (оба поддерживаются одновременно):
- Email + password (bcrypt)
- OAuth 2.0: Google, Apple

## Важные замечания

- `get_async_session` в `db_depends.py` должен быть async — поменять перед подключением к роутерам
- `add_participant` имеет TOCTOU race condition — ловить `IntegrityError` на сервисном уровне
- Soft delete через `deleted_at` на `users`, `events`, `galleries`, `photos`
- Soft delete галереи не каскадится на фото — сервис должен удалять явно