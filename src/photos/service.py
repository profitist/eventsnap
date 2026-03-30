from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import config
from src.models.event import Event
from src.models.gallery import Gallery
from src.models.photo import Photo
from src.photos.schemas import PhotoUploadUrlRequest
from src.repositories.event_repository import EventParticipantRepository, EventRepository
from src.repositories.gallery_repository import GalleryRepository
from src.repositories.photo_repository import PhotoRepository
from src.s3.client import S3Client, S3Error
from src.s3.keys import photo_original_key


class PhotoService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = EventRepository(session)
        self._participants = EventParticipantRepository(session)
        self._galleries = GalleryRepository(session)
        self._photos = PhotoRepository(session)

    async def create_upload_url(
        self,
        event_id: UUID,
        user_id: UUID,
        data: PhotoUploadUrlRequest,
        s3: S3Client,
    ) -> tuple[Photo, str]:
        event = await self._get_event_for_member(event_id, user_id)
        gallery = await self._get_gallery_or_404(event.id)

        photo_id = uuid4()
        original_key = photo_original_key(event.id, photo_id, data.content_type)
        moderation_status = "pending" if gallery.moderation_enabled else "approved"

        try:
            photo = await self._photos.create(
                id=photo_id,
                gallery_id=gallery.id,
                uploader_id=user_id,
                original_s3_key=original_key,
                original_filename=data.filename,
                file_size_bytes=data.file_size_bytes,
                mime_type=data.content_type,
                width_px=data.width_px,
                height_px=data.height_px,
                moderation_status=moderation_status,
                moderated_at=None if moderation_status == "pending" else datetime.now(tz=timezone.utc),
            )
            upload_url = await s3.generate_presigned_upload_url(
                original_key,
                data.content_type,
            )
            await self._session.commit()
            return photo, upload_url
        except S3Error as exc:
            await self._session.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            )

    async def list_approved_for_event(
        self,
        event_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Photo], int]:
        event = await self._get_event_for_member(event_id, user_id)
        gallery = await self._get_gallery_or_404(event.id)
        items = await self._photos.get_approved_for_gallery(
            gallery.id,
            limit=limit,
            offset=offset,
        )
        return items, len(items)

    async def delete_photo(self, photo_id: UUID, user_id: UUID) -> None:
        photo, _, event = await self._get_photo_with_context(photo_id)
        if photo.uploader_id != user_id and event.organizer_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only uploader or organizer can delete this photo",
            )
        await self._photos.soft_delete(photo)
        await self._session.commit()

    async def list_pending_for_event(
        self,
        event_id: UUID,
        user_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Photo], int]:
        event = await self._get_event_for_organizer(event_id, user_id)
        gallery = await self._get_gallery_or_404(event.id)
        items = await self._photos.get_pending_for_gallery(
            gallery.id,
            limit=limit,
            offset=offset,
        )
        return items, len(items)

    async def get_pending_count_for_event(self, event_id: UUID, user_id: UUID) -> int:
        event = await self._get_event_for_organizer(event_id, user_id)
        gallery = await self._get_gallery_or_404(event.id)
        return await self._photos.get_pending_count_for_gallery(gallery.id)

    async def approve_photo(
        self,
        photo_id: UUID,
        user_id: UUID,
        *,
        comment: str | None = None,
    ) -> Photo:
        photo, _, event = await self._get_photo_with_context(photo_id)
        if event.organizer_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organizer can moderate photos",
            )
        if photo.moderation_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Photo is already moderated",
            )

        photo = await self._photos.approve(photo, moderated_by_id=user_id, comment=comment)
        await self._session.commit()
        await self._session.refresh(photo)
        return photo

    async def reject_photo(self, photo_id: UUID, user_id: UUID, *, comment: str) -> Photo:
        photo, _, event = await self._get_photo_with_context(photo_id)
        if event.organizer_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organizer can moderate photos",
            )
        if photo.moderation_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Photo is already moderated",
            )

        photo = await self._photos.reject(photo, moderated_by_id=user_id, comment=comment)
        await self._session.commit()
        await self._session.refresh(photo)
        return photo

    async def _get_event_for_member(self, event_id: UUID, user_id: UUID) -> Event:
        event = await self._events.get_active_by_id(event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )

        is_member = await self._participants.is_participant(event.id, user_id)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant of this event",
            )
        return event

    async def _get_event_for_organizer(self, event_id: UUID, user_id: UUID) -> Event:
        event = await self._events.get_active_by_id(event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        if event.organizer_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the event organizer can perform this action",
            )
        return event

    async def _get_gallery_or_404(self, event_id: UUID) -> Gallery:
        gallery = await self._galleries.get_by_event_id(event_id)
        if gallery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gallery not found",
            )
        return gallery

    async def _get_photo_with_context(self, photo_id: UUID) -> tuple[Photo, Gallery, Event]:
        photo = await self._photos.get_by_id(photo_id)
        if photo is None or photo.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Photo not found",
            )

        gallery = await self._galleries.get_active_by_id(photo.gallery_id)
        if gallery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gallery not found",
            )

        event = await self._events.get_active_by_id(gallery.event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )

        return photo, gallery, event

    @staticmethod
    def upload_ttl_seconds() -> int:
        return config.S3_PRESIGN_UPLOAD_TTL
