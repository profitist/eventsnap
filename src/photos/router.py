from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.db_depends import get_async_session
from src.models.photo import Photo
from src.models.user import User
from src.photos.schemas import (
    PendingCountResponse,
    PhotoApproveRequest,
    PhotoListResponse,
    PhotoRejectRequest,
    PhotoResponse,
    PhotoUploadUrlRequest,
    PhotoUploadUrlResponse,
)
from src.photos.service import PhotoService
from src.s3.client import S3Client, get_s3_client

router = APIRouter(tags=["photos"])


def _to_photo_response(photo: Photo, s3: S3Client) -> PhotoResponse:
    return PhotoResponse(
        **PhotoResponse.model_validate(photo).model_dump(),
        original_url=s3.build_public_url(photo.original_s3_key),
        thumbnail_url=s3.build_public_url(photo.thumbnail_s3_key) if photo.thumbnail_s3_key else None,
    )


@router.post(
    "/events/{event_id}/photos/upload-url",
    response_model=PhotoUploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_photo_upload_url(
    event_id: UUID,
    body: PhotoUploadUrlRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> PhotoUploadUrlResponse:
    service = PhotoService(session)
    photo, upload_url = await service.create_upload_url(event_id, user.id, body, s3)
    return PhotoUploadUrlResponse(
        photo_id=photo.id,
        upload_url=upload_url,
        s3_key=photo.original_s3_key,
        expires_in=service.upload_ttl_seconds(),
        moderation_status=photo.moderation_status,
    )


@router.get("/events/{event_id}/photos", response_model=PhotoListResponse)
async def list_approved_photos(
    event_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> PhotoListResponse:
    service = PhotoService(session)
    items, total = await service.list_approved_for_event(
        event_id,
        user.id,
        limit=limit,
        offset=offset,
    )
    return PhotoListResponse(
        items=[_to_photo_response(photo, s3) for photo in items],
        total=total,
    )


@router.get("/events/{event_id}/photos/pending", response_model=PhotoListResponse)
async def list_pending_photos(
    event_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> PhotoListResponse:
    service = PhotoService(session)
    items, total = await service.list_pending_for_event(
        event_id,
        user.id,
        limit=limit,
        offset=offset,
    )
    return PhotoListResponse(
        items=[_to_photo_response(photo, s3) for photo in items],
        total=total,
    )


@router.get("/events/{event_id}/photos/pending/count", response_model=PendingCountResponse)
async def pending_photos_count(
    event_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PendingCountResponse:
    service = PhotoService(session)
    total = await service.get_pending_count_for_event(event_id, user.id)
    return PendingCountResponse(total=total)


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    service = PhotoService(session)
    await service.delete_photo(photo_id, user.id)


@router.post("/photos/{photo_id}/approve", response_model=PhotoResponse)
async def approve_photo(
    photo_id: UUID,
    body: PhotoApproveRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> PhotoResponse:
    service = PhotoService(session)
    photo = await service.approve_photo(photo_id, user.id, comment=body.comment)
    return _to_photo_response(photo, s3)


@router.post("/photos/{photo_id}/reject", response_model=PhotoResponse)
async def reject_photo(
    photo_id: UUID,
    body: PhotoRejectRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> PhotoResponse:
    service = PhotoService(session)
    photo = await service.reject_photo(photo_id, user.id, comment=body.comment)
    return _to_photo_response(photo, s3)
