import enum
import uuid

from sqlalchemy import String, Text, DATETIME, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime
from .base import Base
from .user import User


class EventStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    title: Mapped[str] = mapped_column(String(150), nullable=False)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    creator_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    qr_link: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DATETIME, nullable=False, default_factory=datetime.utcnow
    )

    deleted_at: Mapped[datetime] = mapped_column(DATETIME, nullable=True)

    status: Mapped[EventStatus] = mapped_column(
        String(20), nullable=False, default=EventStatus.DRAFT
    )

    creator: Mapped["User"] = relationship("User", back_populates="events_with_creator")
