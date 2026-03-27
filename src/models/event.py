
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.gallery import Gallery
    from src.models.user import User


class Event(Base):
    """
    An event created by an organizer.
    One event owns exactly one gallery (created alongside the event).
    The QR code is a stable token used to admit participants.
    """

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organizer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status lifecycle: draft -> active -> finished -> archived
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "active", "finished", "archived", name="event_status_enum"),
        nullable=False,
        server_default="draft",
        index=True,
    )

    # Cover image stored in S3; only the key is persisted
    cover_s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Location
    venue_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    venue_address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # NUMERIC(10,7) gives ~11mm precision, sufficient for geolocation
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)

    # Scheduled time window
    starts_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Stable token embedded into the QR code URL
    qr_token: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, default=lambda: uuid.uuid4().hex
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    organizer: Mapped[Optional["User"]] = relationship(
        "User", back_populates="events_organized"
    )
    gallery: Mapped[Optional["Gallery"]] = relationship(
        "Gallery", back_populates="event", uselist=False, cascade="all, delete-orphan"
    )
    participants: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant", back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_events_ends_after_starts",
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_events_coords_both_or_neither",
        ),
        # Partial index: fast lookup of active events, skipping archived/deleted rows
        Index(
            "ix_events_status_active",
            "status",
            postgresql_where="status IN ('draft', 'active') AND deleted_at IS NULL",
        ),
    )


class EventParticipant(Base):
    """
    Join table: User <-> Event.
    Created automatically when a user scans the event QR code.
    Per-event role can be 'organizer' (co-host) or 'attendee'.
    """

    __tablename__ = "event_participants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Role within this specific event
    role: Mapped[str] = mapped_column(
        SAEnum("organizer", "attendee", name="participant_role_enum"),
        nullable=False,
        server_default="attendee",
    )

    # Timestamp when the QR was scanned / user was added
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    event: Mapped["Event"] = relationship("Event", back_populates="participants")
    user: Mapped["User"] = relationship("User", back_populates="participations")

    __table_args__ = (
        # A user joins an event exactly once
        UniqueConstraint("event_id", "user_id", name="uq_event_participants_event_user"),
    )