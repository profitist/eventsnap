import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional


from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.event import Event
    from src.models.photo import Photo


class Gallery(Base):
    """
    One gallery per event (1:1).
    The gallery is the container for all photos uploaded to that event.
    """

    __tablename__ = "galleries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # When False, uploaded photos skip the moderation queue and are set to
    # 'approved' immediately. When True (default), photos start as 'pending'.
    moderation_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
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

    event: Mapped["Event"] = relationship("Event", back_populates="gallery")
    photos: Mapped[list["Photo"]] = relationship(
        "Photo", back_populates="gallery", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Enforces the 1:1 relationship with Event at the DB level
        UniqueConstraint("event_id", name="uq_galleries_event_id"),
    )