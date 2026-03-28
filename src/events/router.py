from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.db.db_depends import get_async_session
from src.events.schemas import (
    EventCreateRequest,
    EventListResponse,
    EventResponse,
    EventUpdateRequest,
)
from src.events.service import EventService
from src.models.user import User

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


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> EventResponse:
    service = EventService(session)
    event = await service.get_or_404(event_id)
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
