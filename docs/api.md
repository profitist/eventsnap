# EventSnap API (MVP)

Этот документ описывает целевой API-контракт для MVP.
Статус каждого метода:
- `реализован` — уже есть в коде
- `запланирован` — должен быть добавлен

Пошаговые пользовательские сценарии для фронтенда см. в `docs/frontend-flows.md`.

## Общие правила

- Формат API: JSON over HTTP
- Аутентификация: `Authorization: Bearer <access_token>`
- Пагинация: `limit`, `offset` (где применимо)
- Дата/время: ISO 8601 (UTC)
- Soft delete: удаленные сущности обычно не возвращаются в выдаче

## Auth

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| POST | `/auth/register` | - | Регистрация по email + password | реализован |
| POST | `/auth/login` | - | Логин по email + password | реализован |
| POST | `/auth/refresh` | - | Обновление access/refresh токенов | реализован |
| GET | `/auth/me` | Bearer | Профиль текущего пользователя | реализован |
| POST | `/auth/oauth/google` | - | Вход/регистрация через Google OAuth | отменён |

## Users (профиль)

Поле аватара в БД: `users.avatar_s3_key` (храним именно S3 key, а не бинарные данные).

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| PATCH | `/users/me` | Bearer | Обновить профиль (например, `display_name`) | реализован |
| POST | `/users/me/avatar/upload-url` | Bearer | Получить presigned URL для загрузки аватара | реализован |
| POST | `/users/me/avatar/complete` | Bearer | Подтвердить загрузку аватара и сохранить `avatar_s3_key` | реализован |

### `PATCH /users/me`

Пример запроса:

```json
{
  "display_name": "Иван Михайлов"
}
```

### `POST /users/me/avatar/upload-url`

Пример запроса:

```json
{
  "content_type": "image/jpeg"
}
```

Пример ответа:

```json
{
  "upload_url": "https://s3.example.com/...",
  "s3_key": "avatars/a1b2c3d4.../avatar.jpg",
  "expires_in": 900
}
```

### `POST /users/me/avatar/complete`

Пример запроса:

```json
{
  "s3_key": "avatars/a1b2c3d4.../avatar.jpg"
}
```

## Events

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| POST | `/events` | Bearer | Создать событие | реализован |
| GET | `/events` | Bearer | Список событий пользователя (`role=organizer|participant|all`) | реализован |
| GET | `/events/{event_id}` | Bearer | Получить событие по ID (только участник/организатор) | реализован |
| PATCH | `/events/{event_id}` | Bearer | Обновить событие (организатор) | реализован |
| DELETE | `/events/{event_id}` | Bearer | Soft delete события (организатор) | реализован |
| POST | `/events/{event_id}/cover/upload-url` | Bearer (организатор) | Получить presigned URL для обложки события | реализован |
| POST | `/events/{event_id}/cover/complete` | Bearer (организатор) | Подтвердить загрузку обложки и сохранить `cover_s3_key` | реализован |

### `POST /events/{event_id}/cover/upload-url`

Пример запроса:

```json
{
  "content_type": "image/jpeg"
}
```

Пример ответа:

```json
{
  "upload_url": "https://s3.example.com/...",
  "s3_key": "covers/a1b2c3d4.../cover.jpg",
  "expires_in": 900
}
```

### `POST /events/{event_id}/cover/complete`

Пример запроса:

```json
{
  "s3_key": "covers/a1b2c3d4.../cover.jpg"
}
```

## QR и участники

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| GET | `/events/{event_id}/join-link` | Bearer (организатор) | Получить join URL/данные для генерации QR | реализован |
| POST | `/events/join` | Bearer | Вход в событие по `qr_token` (автодобавление участником) | реализован |
| GET | `/events/{event_id}/participants` | Bearer | Список участников события | реализован |

`GET /events/{event_id}/join-link` возвращает `qr_token` и `join_path`.
`POST /events/join` возвращает `{ event, already_joined }`.

### `POST /events/join`

Пример запроса:

```json
{
  "qr_token": "a1b2c3d4..."
}
```

## Gallery

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| GET | `/events/{event_id}/gallery` | Bearer (участник/организатор) | Получить метаданные галереи и настройки | реализован |
| PATCH | `/events/{event_id}/gallery` | Bearer (организатор) | Обновить настройки галереи (`moderation_enabled`) | реализован |

## Photos

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| POST | `/events/{event_id}/photos/upload-url` | Bearer (участник/организатор) | Создать `Photo`, вернуть presigned URL для прямой загрузки в S3 | реализован |
| GET | `/events/{event_id}/photos` | Bearer (участник/организатор) | Лента одобренных фото галереи | реализован |
| DELETE | `/photos/{photo_id}` | Bearer | Удалить фото (автор фото или организатор) | реализован |

### `POST /events/{event_id}/photos/upload-url`

Пример запроса:

```json
{
  "filename": "IMG_1024.JPG",
  "content_type": "image/jpeg",
  "file_size_bytes": 2481234
}
```

Пример ответа:

```json
{
  "photo_id": "0ecfdb90-4126-42c5-a61d-7bcc8e7eb7f2",
  "upload_url": "https://s3.example.com/...",
  "s3_key": "photos/<event>/<photo>/original.jpg",
  "expires_in": 900
}
```

## Moderation

| Метод | Путь | Auth | Описание | Статус |
|---|---|---|---|---|
| GET | `/events/{event_id}/photos/pending` | Bearer (организатор) | Очередь фото на модерацию | реализован |
| GET | `/events/{event_id}/photos/pending/count` | Bearer (организатор) | Количество фото в очереди | реализован |
| POST | `/photos/{photo_id}/approve` | Bearer (организатор) | Одобрить фото | реализован |
| POST | `/photos/{photo_id}/reject` | Bearer (организатор) | Отклонить фото с комментарием | реализован |

### `POST /photos/{photo_id}/reject`

Пример запроса:

```json
{
  "comment": "Фото не относится к событию"
}
```

## Базовые HTTP-ошибки

- `400` — ошибка валидации или бизнес-ограничения
- `401` — невалидный/просроченный токен или отсутствие авторизации
- `403` — недостаточно прав (например, не организатор)
- `404` — сущность не найдена или soft-deleted
- `409` — конфликт (например, email уже зарегистрирован)
