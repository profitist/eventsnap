"""
Repository layer for EventSnap.

Each repository wraps one (or a group of closely related) SQLAlchemy models
and exposes async query/mutation helpers. Business logic stays in the service
layer; repositories only speak SQL.

Public surface:
    BaseRepository              — generic CRUD, imported for type hints
    UserRepository              — User model queries
    UserPasswordCredentialRepository
    UserOAuthAccountRepository
    EventRepository             — Event model queries
    EventParticipantRepository  — EventParticipant join-table queries
    GalleryRepository           — Gallery model queries
    PhotoRepository             — Photo model queries + moderation helpers
"""

from src.repositories.base import BaseRepository
from src.repositories.event_repository import EventParticipantRepository, EventRepository
from src.repositories.gallery_repository import GalleryRepository
from src.repositories.photo_repository import PhotoRepository
from src.repositories.user_repository import (
    UserOAuthAccountRepository,
    UserPasswordCredentialRepository,
    UserRepository,
)

__all__ = [
    "BaseRepository",
    "UserRepository",
    "UserPasswordCredentialRepository",
    "UserOAuthAccountRepository",
    "EventRepository",
    "EventParticipantRepository",
    "GalleryRepository",
    "PhotoRepository",
]