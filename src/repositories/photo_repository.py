"""
Photo repository.

Covers the three main access patterns:
  1. Gallery feed (approved photos, paginated, sort_order ASC then created_at ASC)
  2. Moderation queue (pending photos for a gallery, newest first)
  3. Individual photo management (uploader-scoped, admin ops)

Index notes (defined in Photo.__table_args__):
  - ix_photos_gallery_approved  → gallery feed queries
  - ix_photos_pending_moderation → moderation queue queries
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from src.models.photo import Photo
from src.repositories.base import BaseRepository


class PhotoRepository(BaseRepository[Photo]):
    model = Photo

    # ------------------------------------------------------------------
    # Gallery feed
    # ------------------------------------------------------------------

    async def get_approved_for_gallery(
        self,
        gallery_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Photo]:
        """
        Return approved, non-deleted photos for the public gallery feed.

        Ordered by sort_order ASC, then created_at ASC so that organiser
        reordering is reflected immediately, and ties break chronologically.

        Uses the ix_photos_gallery_approved partial index.
        """
        result = await self._session.execute(
            select(Photo)
            .where(
                Photo.gallery_id == gallery_id,
                Photo.moderation_status == "approved",
                Photo.deleted_at.is_(None),
            )
            .order_by(Photo.sort_order.asc(), Photo.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Moderation queue
    # ------------------------------------------------------------------

    async def get_pending_for_gallery(
        self,
        gallery_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Photo]:
        """
        Return photos awaiting moderation for a specific gallery.

        Oldest first (created_at ASC) so moderators work through the
        backlog in FIFO order. Uses ix_photos_pending_moderation.
        """
        result = await self._session.execute(
            select(Photo)
            .where(
                Photo.gallery_id == gallery_id,
                Photo.moderation_status == "pending",
                Photo.deleted_at.is_(None),
            )
            .order_by(Photo.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_pending_count_for_gallery(self, gallery_id: UUID) -> int:
        """
        Return the number of photos pending moderation.
        Useful for badge counters in the organiser dashboard.
        """
        from sqlalchemy import func, select as sa_select

        result = await self._session.execute(
            sa_select(func.count(Photo.id)).where(
                Photo.gallery_id == gallery_id,
                Photo.moderation_status == "pending",
                Photo.deleted_at.is_(None),
            )
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Moderation actions
    # ------------------------------------------------------------------

    async def approve(
        self,
        photo: Photo,
        moderated_by_id: UUID,
        comment: str | None = None,
    ) -> Photo:
        """
        Transition a photo from *pending* to *approved*.
        Records who moderated it and when.
        """
        return await self.update(
            photo,
            moderation_status="approved",
            moderated_by_id=moderated_by_id,
            moderated_at=datetime.now(tz=timezone.utc),
            moderation_comment=comment,
        )

    async def reject(
        self,
        photo: Photo,
        moderated_by_id: UUID,
        comment: str | None = None,
    ) -> Photo:
        """
        Transition a photo from *pending* to *rejected*.
        A rejection reason should always be provided to help the uploader.
        """
        return await self.update(
            photo,
            moderation_status="rejected",
            moderated_by_id=moderated_by_id,
            moderated_at=datetime.now(tz=timezone.utc),
            moderation_comment=comment,
        )

    # ------------------------------------------------------------------
    # Uploader-scoped queries
    # ------------------------------------------------------------------

    async def get_by_uploader(
        self,
        uploader_id: UUID,
        *,
        gallery_id: UUID | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Photo]:
        """
        Return photos uploaded by a specific user.

        Optionally scoped to a single gallery (e.g. "my uploads in this event").
        """
        stmt = (
            select(Photo)
            .where(Photo.uploader_id == uploader_id)
            .order_by(Photo.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if gallery_id is not None:
            stmt = stmt.where(Photo.gallery_id == gallery_id)
        if not include_deleted:
            stmt = stmt.where(Photo.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Thumbnail tracking (background worker integration)
    # ------------------------------------------------------------------

    async def set_thumbnail_key(self, photo: Photo, thumbnail_s3_key: str) -> Photo:
        """
        Record the S3 key of the generated thumbnail.
        Called by the background worker after thumbnail generation completes.
        """
        return await self.update(photo, thumbnail_s3_key=thumbnail_s3_key)

    async def get_without_thumbnail(
        self,
        *,
        limit: int = 100,
    ) -> list[Photo]:
        """
        Return approved, non-deleted photos that still lack a thumbnail.
        Used by the thumbnail-generation worker to find its work queue.
        """
        result = await self._session.execute(
            select(Photo)
            .where(
                Photo.thumbnail_s3_key.is_(None),
                Photo.moderation_status == "approved",
                Photo.deleted_at.is_(None),
            )
            .order_by(Photo.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def soft_delete(self, photo: Photo) -> Photo:
        """
        Soft-delete a photo. The S3 objects are NOT removed here —
        the service layer should schedule their deletion separately.
        """
        return await self.update(
            photo,
            deleted_at=datetime.now(tz=timezone.utc),
        )