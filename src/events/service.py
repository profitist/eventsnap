from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.events.schemas import EventCreateRequest, EventUpdateRequest
from src.models.event import Event, EventParticipant
from src.models.gallery import Gallery
from src.repositories.event_repository import EventParticipantRepository, EventRepository
from src.repositories.gallery_repository import GalleryRepository


class EventService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events = EventRepository(session)
        self._participants = EventParticipantRepository(session)
        self._galleries = GalleryRepository(session)

    async def create(self, organizer_id: UUID, data: EventCreateRequest) -> Event:
        event = await self._events.create(
            organizer_id=organizer_id,
            title=data.title,
            description=data.description,
            venue_name=data.venue_name,
            venue_address=data.venue_address,
            latitude=data.latitude,
            longitude=data.longitude,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
        )

        await self._galleries.create(event_id=event.id)

        await self._participants.add_participant(
            event_id=event.id,
            user_id=organizer_id,
            role="organizer",
        )

        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def get_or_404(self, event_id: UUID) -> Event:
        event = await self._events.get_active_by_id(event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found",
            )
        return event

    async def get_for_member_or_403(self, event_id: UUID, user_id: UUID) -> Event:
        event = await self.get_or_404(event_id)
        await self._ensure_member(event.id, user_id)
        return event

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        role: str = "organizer",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Event], int]:
        if role == "organizer":
            items = await self._events.get_by_organizer(
                user_id, limit=limit, offset=offset,
            )
            total = len(items)

        elif role == "participant":
            participations = await self._participants.get_events_for_user(
                user_id, limit=limit, offset=offset,
            )
            items = []
            for p in participations:
                event = await self._events.get_active_by_id(p.event_id)
                if event is not None:
                    items.append(event)
            total = len(items)

        else:  # "all"
            organized = await self._events.get_by_organizer(
                user_id, limit=limit, offset=offset,
            )
            participations = await self._participants.get_events_for_user(
                user_id, limit=limit, offset=offset,
            )
            organized_ids = {e.id for e in organized}
            extra = []
            for p in participations:
                if p.event_id not in organized_ids:
                    event = await self._events.get_active_by_id(p.event_id)
                    if event is not None:
                        extra.append(event)
            items = organized + extra
            total = len(items)

        return items, total

    async def update(
        self, event_id: UUID, user_id: UUID, data: EventUpdateRequest,
    ) -> Event:
        event = await self._get_owned_event(event_id, user_id)
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return event

        event = await self._events.update(event, **update_data)
        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def soft_delete(self, event_id: UUID, user_id: UUID) -> None:
        event = await self._get_owned_event(event_id, user_id)
        await self._events.soft_delete(event)
        await self._session.commit()

    async def get_join_link(self, event_id: UUID, user_id: UUID) -> Event:
        return await self._get_owned_event(event_id, user_id)

    async def join_by_qr_token(self, qr_token: str, user_id: UUID) -> tuple[Event, bool]:
        event = await self._events.get_by_qr_token(qr_token)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid or expired QR token",
            )

        existing = await self._participants.get_by_event_and_user(event.id, user_id)
        if existing is not None:
            return event, True

        try:
            await self._participants.add_participant(
                event_id=event.id,
                user_id=user_id,
                role="attendee",
            )
            await self._session.commit()
        except IntegrityError:
            # A concurrent join request may win the unique constraint race.
            await self._session.rollback()
            return event, True

        return event, False

    async def list_participants(
        self,
        event_id: UUID,
        user_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EventParticipant], int]:
        event = await self.get_or_404(event_id)
        await self._ensure_member(event.id, user_id)
        participants = await self._participants.get_participants_for_event(
            event.id,
            limit=limit,
            offset=offset,
        )
        return participants, len(participants)

    async def get_gallery_for_member(self, event_id: UUID, user_id: UUID) -> Gallery:
        event = await self.get_or_404(event_id)
        await self._ensure_member(event.id, user_id)
        gallery = await self._galleries.get_by_event_id(event.id)
        if gallery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gallery not found",
            )
        return gallery

    async def update_gallery(
        self,
        event_id: UUID,
        user_id: UUID,
        *,
        moderation_enabled: bool | None,
    ) -> Gallery:
        event = await self._get_owned_event(event_id, user_id)
        gallery = await self._galleries.get_by_event_id(event.id)
        if gallery is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gallery not found",
            )

        if moderation_enabled is None:
            return gallery

        gallery = await self._galleries.update(
            gallery,
            moderation_enabled=moderation_enabled,
        )
        await self._session.commit()
        await self._session.refresh(gallery)
        return gallery

    async def _get_owned_event(self, event_id: UUID, user_id: UUID) -> Event:
        event = await self.get_or_404(event_id)
        if event.organizer_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the event organizer can perform this action",
            )
        return event

    async def _ensure_member(self, event_id: UUID, user_id: UUID) -> None:
        is_member = await self._participants.is_participant(event_id, user_id)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a participant of this event",
            )
