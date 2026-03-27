# Import all models here so that:
# 1. Alembic env.py can import Base and have all metadata populated.
# 2. Relationship back-references resolve correctly across modules.

from src.models.base import Base
from src.models.event import Event, EventParticipant
from src.models.gallery import Gallery
from src.models.photo import Photo
from src.models.user import User, UserOAuthAccount, UserPasswordCredential

__all__ = [
    "Base",
    "User",
    "UserPasswordCredential",
    "UserOAuthAccount",
    "Event",
    "EventParticipant",
    "Gallery",
    "Photo",
]