"""External identities: bridge GitHub org members to Propel users.

Revision ID: 003
Revises: 002
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("connected_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=50),
            server_default="github",
            nullable=False,
        ),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("external_login", sa.String(length=255), nullable=False),
        sa.Column("external_email", sa.String(length=320), nullable=True),
        sa.Column("external_name", sa.String(length=255), nullable=True),
        sa.Column("github_org_role", sa.String(length=20), nullable=True),
        sa.Column("propel_user_id", sa.Uuid(), nullable=True),
        sa.Column("link_method", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["connected_account_id"], ["connected_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["propel_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_user_id",
            name="uq_external_identity_user",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "external_login",
            name="uq_external_identity_login",
        ),
    )
    op.create_index(
        "ix_external_identities_tenant_id",
        "external_identities",
        ["tenant_id"],
        unique=False,
    )
    # One external identity per Propel user per tenant/provider (only when linked).
    op.create_index(
        "uq_external_identity_propel_user",
        "external_identities",
        ["tenant_id", "provider", "propel_user_id"],
        unique=True,
        postgresql_where=sa.text("propel_user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_external_identity_propel_user", table_name="external_identities")
    op.drop_index("ix_external_identities_tenant_id", table_name="external_identities")
    op.drop_table("external_identities")
