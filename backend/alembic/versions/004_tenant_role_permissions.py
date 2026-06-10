"""Tenant role permissions: configurable per-role permission grants.

Revision ID: 004
Revises: 003
Create Date: 2026-06-09
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default matrix snapshot for the backfill. Intentionally inlined (not
# imported from app code) so the migration stays stable as defaults evolve.
_DEFAULTS: dict[str, list[str]] = {
    "admin": [
        "tenant:read",
        "tenant:update",
        "tenant:delete",
        "members:read",
        "members:assign_role",
        "members:remove",
        "invites:read",
        "invites:revoke",
        "invites:role:admin",
        "invites:role:manager",
        "invites:role:individual",
        "connections:manage",
        "github_identities:manage",
        "ingestion:read",
        "metrics:read",
        "roles:manage",
    ],
    "manager": [
        "tenant:read",
        "members:read",
        "invites:read",
        "invites:revoke",
        "invites:role:manager",
        "invites:role:individual",
        "ingestion:read",
        "metrics:read",
    ],
    "individual": [
        "tenant:read",
        "members:read",
        "ingestion:read",
        "metrics:read",
    ],
}


def upgrade() -> None:
    table = op.create_table(
        "tenant_role_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "admin", "manager", "individual", name="role", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("permission", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "role", "permission", name="uq_tenant_role_permission"
        ),
    )
    op.create_index(
        "ix_tenant_role_permissions_tenant_id",
        "tenant_role_permissions",
        ["tenant_id"],
    )

    # Backfill: seed default grants for every existing tenant.
    conn = op.get_bind()
    tenant_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM tenants"))]
    rows = [
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "role": role,
            "permission": permission,
        }
        for tenant_id in tenant_ids
        for role, permissions in _DEFAULTS.items()
        for permission in permissions
    ]
    if rows:
        op.bulk_insert(table, rows)


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_role_permissions_tenant_id", table_name="tenant_role_permissions"
    )
    op.drop_table("tenant_role_permissions")
