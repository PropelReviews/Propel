"""Drop Zitadel identity columns after the GitHub OAuth cutover.

Revision ID: 010
Revises: 009
Create Date: 2026-06-18

GitHub OAuth replaced Zitadel as the identity provider, so the Zitadel subject
columns (`users.zitadel_user_id`, `tenants.zitadel_org_id`) are no longer
written or read. Drop them and their unique indexes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_users_zitadel_user_id", table_name="users")
    op.drop_column("users", "zitadel_user_id")
    op.drop_index("ix_tenants_zitadel_org_id", table_name="tenants")
    op.drop_column("tenants", "zitadel_org_id")


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("zitadel_org_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_tenants_zitadel_org_id",
        "tenants",
        ["zitadel_org_id"],
        unique=True,
    )
    op.add_column(
        "users",
        sa.Column("zitadel_user_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_users_zitadel_user_id",
        "users",
        ["zitadel_user_id"],
        unique=True,
    )
