import enum
import uuid

from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from datetime import datetime

from .base import Base


class UserRole(str, enum.Enum):
    ADMIN = 'admin'
    COMMON_USER = 'user'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)

    last_name: Mapped[str] = mapped_column(String(50), nullable=False)

    middle_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    created_at: Mapped[datetime | None] = mapped_column(String(255), nullable=False, default_factory=datetime.utcnow)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(String(20), nullable=False, default=UserRole.COMMON_USER)

    # События которые были созданы пользователем
    events_with_creator: Mapped[list['Event']] = relationship('Event', back_populates='creator')

    photos: Mapped[list['Photo']] = relationship('Photo', back_populates='author')



