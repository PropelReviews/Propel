"""Waitlist subscribers: emails captured from the landing page.

Revision ID: 005
Revises: 004
Create Date: 2026-06-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_subscribers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_waitlist_subscribers_email"),
        "waitlist_subscribers",
        ["email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_waitlist_subscribers_email"), table_name="waitlist_subscribers"
    )
    op.drop_table("waitlist_subscribers")
