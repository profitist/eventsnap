"""
Event and EventParticipant repositories.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.event import Event, EventParticipant
from src.repositories.base import BaseRepository


class EventRepository(BaseRepository[Event]):
    model = Event

    # ------------------------------------------------------------------
    # Lookup methods
    # ------------------------------------------------------------------

    async def get_by_qr_token(self, qr_token: str) -> Event | None:
        """
        Resolve a QR-scan request to an event.
        Returns None for deleted events so the scan appears invalid.
        """
        result = await self._session.execute(
            select(Event).where(
                Event.qr_token == qr_token,
                Event.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_id(self, event_id: UUID) -> Event | None:
        """Return an event that has not been soft-deleted."""
        result = await self._session.execute(
            select(Event).where(
                Event.id == event_id,
                Event.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_organizer(
        self,
        organizer_id: UUID,
        *,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """
        Return all events owned by the given organizer.
        Newest first by default (created_at DESC).
        """
        stmt = (
            select(Event)
            .where(Event.organizer_id == organizer_id)
            .order_by(Event.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if not include_deleted:
            stmt = stmt.where(Event.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_status(
        self,
        status: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """
        Return non-deleted events in a specific lifecycle status.

        Valid statuses: draft | active | finished | archived
        This method uses the partial index ix_events_status_active for
        draft/active queries.
        """
        result = await self._session.execute(
            select(Event)
            .where(Event.status == status, Event.deleted_at.is_(None))
            .order_by(Event.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_with_gallery(self, event_id: UUID) -> Event | None:
        """
        Fetch an event together with its gallery in one round-trip.
        Avoids a lazy-load when the caller needs gallery.id immediately.
        """
        result = await self._session.execute(
            select(Event)
            .options(selectinload(Event.gallery))
            .where(Event.id == event_id, Event.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_with_participants(self, event_id: UUID) -> Event | None:
        """
        Fetch an event together with the full participants list.
        Use only when participant count is bounded (< a few hundred).
        For large events, use EventParticipantRepository directly with pagination.
        """
        result = await self._session.execute(
            select(Event)
            .options(selectinload(Event.participants))
            .where(Event.id == event_id, Event.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    async def soft_delete(self, event: Event) -> Event:
        """Mark an event as deleted. Does not alter its status."""
        return await self.update(
            event,
            deleted_at=datetime.now(tz=timezone.utc),
        )


class EventParticipantRepository(BaseRepository[EventParticipant]):
    model = EventParticipant

    # ------------------------------------------------------------------
    # Lookup methods
    # ------------------------------------------------------------------

    async def get_by_event_and_user(
        self, event_id: UUID, user_id: UUID
    ) -> EventParticipant | None:
        """
        Check whether a user is already a participant in an event.
        Used before adding a new row to respect the unique constraint.
        """
        result = await self._session.execute(
            select(EventParticipant).where(
                EventParticipant.event_id == event_id,
                EventParticipant.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_participants_for_event(
        self,
        event_id: UUID,
        *,
        role: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventParticipant]:
        """
        Return participants for an event, optionally filtered by role.

        Role values: organizer | attendee
        """
        stmt = (
            select(EventParticipant)
            .where(EventParticipant.event_id == event_id)
            .order_by(EventParticipant.joined_at.asc())
            .limit(limit)
            .offset(offset)
        )
        if role is not None:
            stmt = stmt.where(EventParticipant.role == role)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_events_for_user(
        self,
        user_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EventParticipant]:
        """
        Return all EventParticipant rows for a user (their joined events).
        Ordered by most recently joined first.
        """
        result = await self._session.execute(
            select(EventParticipant)
            .where(EventParticipant.user_id == user_id)
            .order_by(EventParticipant.joined_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def is_participant(self, event_id: UUID, user_id: UUID) -> bool:
        """Convenience boolean check — no extra data loaded."""
        row = await self.get_by_event_and_user(event_id, user_id)
        return row is not None

    # ------------------------------------------------------------------
    # QR join flow
    # ------------------------------------------------------------------

    async def add_participant(
        self,
        event_id: UUID,
        user_id: UUID,
        role: str = "attendee",
    ) -> EventParticipant:
        """
        Add a user to an event.

        Callers must check `is_participant` first if they want a clean error
        rather than an IntegrityError from the unique constraint.
        """
        return await self.create(event_id=event_id, user_id=user_id, role=role)

    async def remove_participant(self, event_id: UUID, user_id: UUID) -> bool:
        """
        Hard-delete the participation row.
        Returns True if removed, False if the user was not a participant.
        """
        participant = await self.get_by_event_and_user(event_id, user_id)
        if participant is None:
            return False
        await self.delete(participant)
        return True