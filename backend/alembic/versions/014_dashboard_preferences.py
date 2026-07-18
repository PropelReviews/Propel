"""Per-user dashboard preference backups.

Revision ID: 014
Revises: 013
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dashboard_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "layout",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            name="uq_dashboard_preferences_tenant_user",
        ),
    )
    op.create_index(
        "ix_dashboard_preferences_tenant_id",
        "dashboard_preferences",
        ["tenant_id"],
    )
    op.create_index(
        "ix_dashboard_preferences_user_id",
        "dashboard_preferences",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_preferences_user_id", table_name="dashboard_preferences")
    op.drop_index(
        "ix_dashboard_preferences_tenant_id", table_name="dashboard_preferences"
    )
    op.drop_table("dashboard_preferences")
