"""
S3 key construction helpers for EventSnap.

All S3 keys used in the application are produced by the functions in this
module. Centralising key construction here means that the key layout is
defined in exactly one place — changing the layout only requires editing
this file.

Key layout:

    photos/{event_id}/{photo_id}/original.{ext}
    photos/{event_id}/{photo_id}/thumb_400.{ext}
    covers/{event_id}/cover.{ext}
    avatars/{user_id}/avatar.{ext}

Rules:
    - UUIDs are stored as plain hex strings without hyphens to keep keys
      short and URL-safe.
    - Extensions are always lowercase.
    - No leading slash — S3 keys must not start with '/'.
"""

from __future__ import annotations

import mimetypes
import uuid

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    "image/avif": "avif",
    "image/tiff": "tiff",
}


def _ext_from_mime(mime_type: str, fallback: str = "bin") -> str:
    """
    Return a lowercase file extension for *mime_type*.

    Checks the hand-maintained _MIME_TO_EXT map first; falls back to the
    stdlib mimetypes module; and finally returns *fallback* if nothing matches.
    """
    if mime_type in _MIME_TO_EXT:
        return _MIME_TO_EXT[mime_type]
    guessed = mimetypes.guess_extension(mime_type)
    if guessed:
        return guessed.lstrip(".").lower()
    return fallback


def _hex(uid: uuid.UUID) -> str:
    """Return a UUID as a plain hex string (no hyphens)."""
    return uid.hex


# ---------------------------------------------------------------------------
# Photo keys
# ---------------------------------------------------------------------------

def photo_original_key(event_id: uuid.UUID, photo_id: uuid.UUID, mime_type: str) -> str:
    """
    S3 key for the original (full-resolution) photo.

    Example:
        photos/a1b2c3d4.../e5f6.../original.jpg
    """
    ext = _ext_from_mime(mime_type)
    return f"photos/{_hex(event_id)}/{_hex(photo_id)}/original.{ext}"


def photo_thumbnail_key(event_id: uuid.UUID, photo_id: uuid.UUID, mime_type: str) -> str:
    """
    S3 key for the ~400px thumbnail.

    The thumbnail is produced by a background worker after upload and shares
    the same MIME type as the original.

    Example:
        photos/a1b2c3d4.../e5f6.../thumb_400.jpg
    """
    ext = _ext_from_mime(mime_type)
    return f"photos/{_hex(event_id)}/{_hex(photo_id)}/thumb_400.{ext}"


def photo_all_keys(event_id: uuid.UUID, photo_id: uuid.UUID, mime_type: str) -> list[str]:
    """
    Return both the original and thumbnail keys for a photo.

    Convenient when scheduling a batch delete — covers the case where the
    thumbnail may or may not have been generated yet.
    """
    return [
        photo_original_key(event_id, photo_id, mime_type),
        photo_thumbnail_key(event_id, photo_id, mime_type),
    ]


# ---------------------------------------------------------------------------
# Event cover key
# ---------------------------------------------------------------------------

def event_cover_key(event_id: uuid.UUID, mime_type: str) -> str:
    """
    S3 key for an event cover image.

    Example:
        covers/a1b2c3d4.../cover.jpg
    """
    ext = _ext_from_mime(mime_type)
    return f"covers/{_hex(event_id)}/cover.{ext}"


# ---------------------------------------------------------------------------
# User avatar key
# ---------------------------------------------------------------------------

def user_avatar_key(user_id: uuid.UUID, mime_type: str) -> str:
    """
    S3 key for a user avatar image.

    Example:
        avatars/a1b2c3d4.../avatar.jpg
    """
    ext = _ext_from_mime(mime_type)
    return f"avatars/{_hex(user_id)}/avatar.{ext}"