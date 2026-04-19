"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ENUM types
    # ------------------------------------------------------------------
    op.execute("CREATE TYPE user_role_enum AS ENUM ('admin', 'organizer', 'guest')")
    op.execute("CREATE TYPE oauth_provider_enum AS ENUM ('google', 'apple')")
    op.execute(
        "CREATE TYPE event_status_enum AS ENUM ('draft', 'active', 'finished', 'archived')"
    )
    op.execute("CREATE TYPE participant_role_enum AS ENUM ('organizer', 'attendee')")
    op.execute(
        "CREATE TYPE photo_moderation_status_enum AS ENUM ('pending', 'approved', 'rejected')"
    )

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("avatar_s3_key", sa.String(512), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin",
                "organizer",
                "guest",
                name="user_role_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="guest",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # user_password_credentials
    # ------------------------------------------------------------------
    op.create_table(
        "user_password_credentials",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", name="uq_user_password_credentials_user_id"),
    )
    op.create_index(
        "ix_user_password_credentials_user_id", "user_password_credentials", ["user_id"]
    )

    # ------------------------------------------------------------------
    # user_oauth_accounts
    # ------------------------------------------------------------------
    op.create_table(
        "user_oauth_accounts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            postgresql.ENUM(
                "google",
                "apple",
                name="oauth_provider_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name="uq_oauth_provider_provider_user_id",
        ),
    )
    op.create_index("ix_user_oauth_accounts_user_id", "user_oauth_accounts", ["user_id"])

    # ------------------------------------------------------------------
    # events
    # ------------------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "organizer_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft", "active", "finished", "archived",
                name="event_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("cover_s3_key", sa.String(512), nullable=True),
        sa.Column("venue_name", sa.String(255), nullable=True),
        sa.Column("venue_address", sa.String(512), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("qr_token", sa.String(128), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_events_ends_after_starts",
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_events_coords_both_or_neither",
        ),
    )
    op.create_index("ix_events_organizer_id", "events", ["organizer_id"])
    op.create_index("ix_events_status", "events", ["status"])
    op.create_index("ix_events_qr_token", "events", ["qr_token"], unique=True)
    # Partial index for active/draft events dashboard queries
    op.create_index(
        "ix_events_status_active",
        "events",
        ["status"],
        postgresql_where=sa.text("status IN ('draft', 'active') AND deleted_at IS NULL"),
    )

    # ------------------------------------------------------------------
    # event_participants
    # ------------------------------------------------------------------
    op.create_table(
        "event_participants",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "event_id",
            sa.UUID(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            postgresql.ENUM(
                "organizer",
                "attendee",
                name="participant_role_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="attendee",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_participants_event_user"),
    )
    op.create_index("ix_event_participants_event_id", "event_participants", ["event_id"])
    op.create_index("ix_event_participants_user_id", "event_participants", ["user_id"])

    # ------------------------------------------------------------------
    # galleries
    # ------------------------------------------------------------------
    op.create_table(
        "galleries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "event_id",
            sa.UUID(),
            sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("event_id", name="uq_galleries_event_id"),
    )
    op.create_index("ix_galleries_event_id", "galleries", ["event_id"])

    # ------------------------------------------------------------------
    # photos
    # ------------------------------------------------------------------
    op.create_table(
        "photos",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "gallery_id",
            sa.UUID(),
            sa.ForeignKey("galleries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploader_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_s3_key", sa.String(512), nullable=False),
        sa.Column("thumbnail_s3_key", sa.String(512), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column(
            "moderation_status",
            postgresql.ENUM(
                "pending", "approved", "rejected",
                name="photo_moderation_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("moderation_comment", sa.String(512), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "moderated_by_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("file_size_bytes > 0", name="ck_photos_file_size_positive"),
        sa.CheckConstraint("width_px > 0", name="ck_photos_width_positive"),
        sa.CheckConstraint("height_px > 0", name="ck_photos_height_positive"),
    )
    op.create_index("ix_photos_gallery_id", "photos", ["gallery_id"])
    op.create_index("ix_photos_uploader_id", "photos", ["uploader_id"])
    op.create_index("ix_photos_moderation_status", "photos", ["moderation_status"])
    # Partial index: approved gallery feed (the hot read path)
    op.create_index(
        "ix_photos_gallery_approved",
        "photos",
        ["gallery_id", "created_at"],
        postgresql_where=sa.text(
            "moderation_status = 'approved' AND deleted_at IS NULL"
        ),
    )
    # Partial index: moderation queue
    op.create_index(
        "ix_photos_pending_moderation",
        "photos",
        ["gallery_id", "created_at"],
        postgresql_where=sa.text(
            "moderation_status = 'pending' AND deleted_at IS NULL"
        ),
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("photos")
    op.drop_table("galleries")
    op.drop_table("event_participants")
    op.drop_table("events")
    op.drop_table("user_oauth_accounts")
    op.drop_table("user_password_credentials")
    op.drop_table("users")

    # Drop enum types
    op.execute("DROP TYPE photo_moderation_status_enum")
    op.execute("DROP TYPE participant_role_enum")
    op.execute("DROP TYPE event_status_enum")
    op.execute("DROP TYPE oauth_provider_enum")
    op.execute("DROP TYPE user_role_enum")
