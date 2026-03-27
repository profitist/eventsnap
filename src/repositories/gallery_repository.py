"""
Gallery repository.

Each Event owns exactly one Gallery (enforced by uq_galleries_event_id).
Most gallery operations are scoped to an event, so event_id is the
primary lookup key alongside the gallery's own UUID.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.gallery import Gallery
from src.repositories.base import BaseRepository


class GalleryRepository(BaseRepository[Gallery]):
    model = Gallery

    # ------------------------------------------------------------------
    # Lookup methods
    # ------------------------------------------------------------------

    async def get_by_event_id(self, event_id: UUID) -> Gallery | None:
        """
        Return the gallery for an event.
        Returns None if the gallery has been soft-deleted.
        """
        result = await self._session.execute(
            select(Gallery).where(
                Gallery.event_id == event_id,
                Gallery.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_event_id_with_photos(self, event_id: UUID) -> Gallery | None:
        """
        Fetch the gallery and eagerly load its photo collection.

        Only call this when the photo count is small (e.g. admin view).
        For public gallery feeds, use PhotoRepository with pagination instead.
        """
        result = await self._session.execute(
            select(Gallery)
            .options(selectinload(Gallery.photos))
            .where(
                Gallery.event_id == event_id,
                Gallery.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(self, gallery_id: UUID) -> Gallery | None:
        """Return a non-deleted gallery by its own primary key."""
        result = await self._session.execute(
            select(Gallery).where(
                Gallery.id == gallery_id,
                Gallery.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def soft_delete(self, gallery: Gallery) -> Gallery:
        """
        Soft-delete the gallery.

        Note: photos are owned by the gallery via cascade at the DB level
        (ON DELETE CASCADE on galleries.id), but soft-deleting the gallery
        does NOT soft-delete photos. If that is needed, the service layer
        should iterate and soft-delete photos before calling this.
        """
        return await self.update(
            gallery,
            deleted_at=datetime.now(tz=timezone.utc),
        )