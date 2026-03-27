"""add moderation_enabled to galleries

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-27 00:00:00.000000

When moderation_enabled is False on a gallery, the upload handler must set
the photo's moderation_status to 'approved' directly instead of 'pending'.
This logic lives in the application layer — the DB column only stores the flag.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "galleries",
        sa.Column(
            "moderation_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    op.drop_column("galleries", "moderation_enabled")