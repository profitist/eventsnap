import uuid
import datetime
import enum

from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String, BigInteger, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .base import Base
from .user import User
from .event import Event


class PhotoStatus(enum.Enum):
    UPLOADING = "uploading"
    ACTIVE = "active"
    DELETED = "deleted"
    REJECTED = "rejected"  # можно замутить ИИ модерацию


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
    )

    url: Mapped[str] = mapped_column(String(1000), nullable=False)

    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)

    status: Mapped[PhotoStatus] = mapped_column(
        Enum(PhotoStatus), default=PhotoStatus.UPLOADING, nullable=False
    )

    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.utcnow, nullable=False
    )

    deleted_at: Mapped[datetime.datetime | None] = mapped_column(nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="photos")

    author: Mapped["User"] = relationship("User", back_populates="photos")
