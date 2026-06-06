"""Platform admin flag and membership role source.

Revision ID: 009
Revises: 008
Create Date: 2026-06-18

Adds the cross-tenant Propel operator flag (`users.is_platform_admin`) and a
`tenant_memberships.role_source` discriminator so the GitHub role sync only
touches GitHub-sourced roles, leaving tenant-admin (`manual`) and Propel
operator (`platform`) overrides sticky.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

role_source_enum = sa.Enum("github", "manual", "platform", name="role_source")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    role_source_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tenant_memberships",
        sa.Column(
            "role_source",
            role_source_enum,
            nullable=False,
            server_default="github",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_memberships", "role_source")
    role_source_enum.drop(op.get_bind(), checkfirst=True)
    op.drop_column("users", "is_platform_admin")
