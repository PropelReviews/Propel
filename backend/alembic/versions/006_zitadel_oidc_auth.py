"""Zitadel OIDC identity fields and RBAC role alignment.

Revision ID: 006
Revises: 005
Create Date: 2026-06-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

membership_status_enum = sa.Enum(
    "invited", "active", "disabled", name="membership_status"
)


def upgrade() -> None:
    # --- users: Zitadel is the auth authority ---
    op.add_column("users", sa.Column("zitadel_user_id", sa.String(255), nullable=True))
    op.create_index(
        op.f("ix_users_zitadel_user_id"), "users", ["zitadel_user_id"], unique=True
    )
    op.alter_column("users", "hashed_password", nullable=True)
    op.alter_column("users", "is_verified", new_column_name="email_verified")
    op.drop_column("users", "is_superuser")

    # --- tenants: 1:1 with Zitadel org ---
    op.add_column("tenants", sa.Column("zitadel_org_id", sa.String(255), nullable=True))
    op.create_index(
        op.f("ix_tenants_zitadel_org_id"), "tenants", ["zitadel_org_id"], unique=True
    )

    # --- memberships: lifecycle status ---
    membership_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tenant_memberships",
        sa.Column(
            "status",
            membership_status_enum,
            nullable=False,
            server_default="active",
        ),
    )

    # Align role names with the auth spec: admin→owner, individual→member.
    op.execute("ALTER TYPE role RENAME VALUE 'admin' TO 'owner'")
    op.execute("ALTER TYPE role RENAME VALUE 'individual' TO 'member'")
    op.execute("ALTER TYPE role ADD VALUE IF NOT EXISTS 'admin'")

    # Remap invite permission keys to match renamed roles.
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:owner' "
        "WHERE permission = 'invites:role:admin'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:member' "
        "WHERE permission = 'invites:role:individual'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tenant_invites SET role = 'member' WHERE role::text = 'member'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:individual' "
        "WHERE permission = 'invites:role:member'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:admin' "
        "WHERE permission = 'invites:role:owner'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET role = 'individual' WHERE role = 'member'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET role = 'admin' WHERE role = 'owner'"
    )

    # Cannot remove 'admin' enum value in Postgres; rename back what we can.
    op.execute("ALTER TYPE role RENAME VALUE 'member' TO 'individual'")
    op.execute("ALTER TYPE role RENAME VALUE 'owner' TO 'admin'")

    op.drop_column("tenant_memberships", "status")
    membership_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_tenants_zitadel_org_id"), table_name="tenants")
    op.drop_column("tenants", "zitadel_org_id")

    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("users", "email_verified", new_column_name="is_verified")
    op.alter_column(
        "users",
        "hashed_password",
        nullable=False,
        server_default=sa.text("''"),
    )
    op.drop_index(op.f("ix_users_zitadel_user_id"), table_name="users")
    op.drop_column("users", "zitadel_user_id")
