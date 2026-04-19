import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.event import Event, EventParticipant
    from src.models.photo import Photo


class User(Base):
    """
    Registered user. Supports email+password and OAuth (Google/Apple).
    Platform-level role stored here; per-event roles live in EventParticipant.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    avatar_s3_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    role: Mapped[str] = mapped_column(
        SAEnum("admin", "organizer", "guest", name="user_role_enum"),
        nullable=False,
        server_default="guest",
    )

    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    # Soft delete — NULL means the account is alive
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
    password_credential: Mapped[Optional["UserPasswordCredential"]] = relationship(
        "UserPasswordCredential",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    oauth_accounts: Mapped[list["UserOAuthAccount"]] = relationship(
        "UserOAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )
    events_organized: Mapped[list["Event"]] = relationship(
        "Event", back_populates="organizer"
    )
    participations: Mapped[list["EventParticipant"]] = relationship(
        "EventParticipant", back_populates="user", cascade="all, delete-orphan"
    )
    photos: Mapped[list["Photo"]] = relationship(
        "Photo",
        foreign_keys="Photo.uploader_id",
        back_populates="uploader",
    )
    moderated_photos: Mapped[list["Photo"]] = relationship(
        "Photo",
        foreign_keys="Photo.moderated_by_id",
        back_populates="moderated_by",
    )


class UserPasswordCredential(Base):
    """
    Bcrypt-hashed password for email+password auth.
    Separate table so OAuth-only users have no row here.
    """

    __tablename__ = "user_password_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="password_credential")

    __table_args__ = (
        # Enforces 1:1 — each user has at most one password row
        UniqueConstraint("user_id", name="uq_user_password_credentials_user_id"),
    )


class UserOAuthAccount(Base):
    """
    OAuth identity linked to a User.
    One user can have both Google and Apple accounts.
    """

    __tablename__ = "user_oauth_accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        SAEnum("google", "apple", name="oauth_provider_enum"), nullable=False
    )
    # Sub / unique ID returned by the OAuth provider
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        # One provider identity cannot be linked to two accounts
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_oauth_provider_provider_user_id"
        ),
    )
