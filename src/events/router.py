from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.db_depends import get_async_session
from src.events.schemas import (
    CoverCompleteRequest,
    CoverUploadUrlRequest,
    CoverUploadUrlResponse,
    EventCreateRequest,
    EventJoinLinkResponse,
    EventJoinRequest,
    EventJoinResponse,
    EventListResponse,
    EventParticipantListResponse,
    EventParticipantResponse,
    EventResponse,
    EventUpdateRequest,
    GalleryResponse,
    GalleryUpdateRequest,
)
from src.events.service import EventService
from src.models.user import User
from src.s3.client import S3Client, get_s3_client

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventResponse:
    service = EventService(session)
    event = await service.create(user.id, body)
    return EventResponse.model_validate(event)


@router.get("", response_model=EventListResponse)
async def list_events(
    role: str = Query("organizer", pattern="^(organizer|participant|all)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventListResponse:
    service = EventService(session)
    items, total = await service.list_for_user(
        user.id, role=role, limit=limit, offset=offset,
    )
    return EventListResponse(
        items=[EventResponse.model_validate(e) for e in items],
        total=total,
    )


@router.post("/join", response_model=EventJoinResponse)
async def join_event_by_qr(
    body: EventJoinRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventJoinResponse:
    service = EventService(session)
    event, already_joined = await service.join_by_qr_token(body.qr_token, user.id)
    return EventJoinResponse(
        event=EventResponse.model_validate(event),
        already_joined=already_joined,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventResponse:
    service = EventService(session)
    event = await service.get_for_member_or_403(event_id, user.id)
    return EventResponse.model_validate(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    body: EventUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventResponse:
    service = EventService(session)
    event = await service.update(event_id, user.id, body)
    return EventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    service = EventService(session)
    await service.soft_delete(event_id, user.id)


@router.post(
    "/{event_id}/cover/upload-url",
    response_model=CoverUploadUrlResponse,
)
async def create_cover_upload_url(
    event_id: UUID,
    body: CoverUploadUrlRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> CoverUploadUrlResponse:
    service = EventService(session)
    upload_url, s3_key = await service.create_cover_upload_url(
        event_id, user.id, body, s3,
    )
    return CoverUploadUrlResponse(
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=service.upload_ttl_seconds(),
    )


@router.post("/{event_id}/cover/complete", response_model=EventResponse)
async def complete_cover_upload(
    event_id: UUID,
    body: CoverCompleteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
    s3: S3Client = Depends(get_s3_client),
) -> EventResponse:
    service = EventService(session)
    event = await service.complete_cover_upload(
        event_id, user.id, body.s3_key, s3,
    )
    return EventResponse.model_validate(event)


@router.get("/{event_id}/join-link", response_model=EventJoinLinkResponse)
async def get_event_join_link(
    event_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventJoinLinkResponse:
    service = EventService(session)
    event = await service.get_join_link(event_id, user.id)
    return EventJoinLinkResponse(
        event_id=event.id,
        qr_token=event.qr_token,
        join_path=f"/join?qr_token={event.qr_token}",
    )


@router.get("/{event_id}/participants", response_model=EventParticipantListResponse)
async def list_event_participants(
    event_id: UUID,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventParticipantListResponse:
    service = EventService(session)
    participants, total = await service.list_participants(
        event_id,
        user.id,
        limit=limit,
        offset=offset,
    )
    items = [
        EventParticipantResponse(
            user_id=p.user_id,
            display_name=p.user.display_name if p.user else "Unknown user",
            avatar_s3_key=p.user.avatar_s3_key if p.user else None,
            role=p.role,
            joined_at=p.joined_at,
        )
        for p in participants
    ]
    return EventParticipantListResponse(items=items, total=total)


@router.get("/{event_id}/gallery", response_model=GalleryResponse)
async def get_gallery(
    event_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GalleryResponse:
    service = EventService(session)
    gallery = await service.get_gallery_for_member(event_id, user.id)
    return GalleryResponse.model_validate(gallery)


@router.patch("/{event_id}/gallery", response_model=GalleryResponse)
async def update_gallery(
    event_id: UUID,
    body: GalleryUpdateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> GalleryResponse:
    service = EventService(session)
    gallery = await service.update_gallery(
        event_id,
        user.id,
        moderation_enabled=body.moderation_enabled,
    )
    return GalleryResponse.model_validate(gallery)
