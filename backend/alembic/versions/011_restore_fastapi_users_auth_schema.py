"""Restore the fastapi-users auth schema after the Zitadel revert.

Revision ID: 011
Revises: 010
Create Date: 2026-07-11

The Zitadel cutover (006) reshaped the auth tables for an identity provider
that was later abandoned: the application code went back to fastapi-users,
but the schema changes were never reverted. Every ORM query on `users` has
been failing with UndefinedColumn (`is_superuser` / `is_verified`) since,
which is why registration and login return 500 in migrated environments.

This revision restores the schema the application actually maps:

- users: rename `email_verified` back to `is_verified`, re-add
  `is_superuser`, backfill NULL `hashed_password` rows with unusable
  random-password hashes, and restore the NOT NULL constraint.
- role enum: remap Zitadel-era `owner` -> `admin` and `member` ->
  `individual` values across tenant_memberships / tenant_invites /
  tenant_role_permissions, restore the invite permission keys, and recreate
  the `role` type with exactly ('admin', 'manager', 'individual').
- drop the Zitadel-era columns nothing on main reads or writes:
  `tenant_memberships.status`, `tenant_memberships.role_source`, and
  `users.is_platform_admin` (plus their enum types).
- oauth_accounts: align with the fastapi-users base table that the ORM maps
  (001 diverged from it) — add the `oauth_name` / `account_id` lookup
  indexes used at OAuth login and make `account_email` NOT NULL.
"""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from fastapi_users.password import PasswordHelper

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_TABLES = ("tenant_memberships", "tenant_invites", "tenant_role_permissions")

membership_status_enum = sa.Enum(
    "invited", "active", "disabled", name="membership_status"
)
role_source_enum = sa.Enum("github", "manual", "platform", name="role_source")


def upgrade() -> None:
    bind = op.get_bind()

    # --- users: restore the columns fastapi-users maps ---
    op.alter_column("users", "email_verified", new_column_name="is_verified")
    op.add_column(
        "users",
        sa.Column(
            "is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Zitadel-era users may have been created without a password hash (or with
    # the empty-string server default from 006's downgrade). Give them an
    # unusable random-password hash (they sign in via OAuth or a future reset
    # flow) so the column can go back to NOT NULL and the hasher never
    # receives a NULL/unknown hash at login.
    password_helper = PasswordHelper()
    user_ids = (
        bind.execute(
            sa.text(
                "SELECT id FROM users "
                "WHERE hashed_password IS NULL OR hashed_password = ''"
            )
        )
        .scalars()
        .all()
    )
    for user_id in user_ids:
        bind.execute(
            sa.text("UPDATE users SET hashed_password = :hash WHERE id = :id"),
            {"hash": password_helper.hash(secrets.token_urlsafe(32)), "id": user_id},
        )
    op.alter_column("users", "hashed_password", nullable=False)

    op.drop_column("users", "is_platform_admin")

    # --- role enum: back to admin / manager / individual ---
    for table in ROLE_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN role TYPE text USING role::text")
    op.execute("DROP TYPE role")

    # Rows that would collide with an existing (tenant, role, permission) grant
    # after the remap are duplicates of it — delete them before updating.
    op.execute(
        "DELETE FROM tenant_role_permissions o USING tenant_role_permissions n "
        "WHERE o.role = 'owner' AND n.role = 'admin' "
        "AND o.tenant_id = n.tenant_id AND o.permission = n.permission"
    )
    op.execute(
        "DELETE FROM tenant_role_permissions o USING tenant_role_permissions n "
        "WHERE o.role = 'member' AND n.role = 'individual' "
        "AND o.tenant_id = n.tenant_id AND o.permission = n.permission"
    )
    for table in ROLE_TABLES:
        op.execute(f"UPDATE {table} SET role = 'admin' WHERE role = 'owner'")
        op.execute(f"UPDATE {table} SET role = 'individual' WHERE role = 'member'")

    # Restore the invite permission keys 006 remapped.
    op.execute(
        "DELETE FROM tenant_role_permissions o USING tenant_role_permissions n "
        "WHERE o.permission = 'invites:role:owner' "
        "AND n.permission = 'invites:role:admin' "
        "AND o.tenant_id = n.tenant_id AND o.role = n.role"
    )
    op.execute(
        "DELETE FROM tenant_role_permissions o USING tenant_role_permissions n "
        "WHERE o.permission = 'invites:role:member' "
        "AND n.permission = 'invites:role:individual' "
        "AND o.tenant_id = n.tenant_id AND o.role = n.role"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:admin' "
        "WHERE permission = 'invites:role:owner'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:individual' "
        "WHERE permission = 'invites:role:member'"
    )

    op.execute("CREATE TYPE role AS ENUM ('admin', 'manager', 'individual')")
    for table in ROLE_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN role TYPE role USING role::role")

    # --- memberships: drop Zitadel-era lifecycle/provenance columns ---
    op.drop_column("tenant_memberships", "status")
    membership_status_enum.drop(bind, checkfirst=True)
    op.drop_column("tenant_memberships", "role_source")
    role_source_enum.drop(bind, checkfirst=True)

    # --- oauth_accounts: align with the fastapi-users base table ---
    op.execute(
        "UPDATE oauth_accounts SET account_email = '' WHERE account_email IS NULL"
    )
    op.alter_column("oauth_accounts", "account_email", nullable=False)
    op.create_index(
        op.f("ix_oauth_accounts_oauth_name"), "oauth_accounts", ["oauth_name"]
    )
    op.create_index(
        op.f("ix_oauth_accounts_account_id"), "oauth_accounts", ["account_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f("ix_oauth_accounts_account_id"), table_name="oauth_accounts")
    op.drop_index(op.f("ix_oauth_accounts_oauth_name"), table_name="oauth_accounts")
    op.alter_column("oauth_accounts", "account_email", nullable=True)

    role_source_enum.create(bind, checkfirst=True)
    op.add_column(
        "tenant_memberships",
        sa.Column(
            "role_source",
            role_source_enum,
            nullable=False,
            server_default="github",
        ),
    )
    membership_status_enum.create(bind, checkfirst=True)
    op.add_column(
        "tenant_memberships",
        sa.Column(
            "status",
            membership_status_enum,
            nullable=False,
            server_default="active",
        ),
    )

    for table in ROLE_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN role TYPE text USING role::text")
    op.execute("DROP TYPE role")
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:owner' "
        "WHERE permission = 'invites:role:admin'"
    )
    op.execute(
        "UPDATE tenant_role_permissions SET permission = 'invites:role:member' "
        "WHERE permission = 'invites:role:individual'"
    )
    for table in ROLE_TABLES:
        op.execute(f"UPDATE {table} SET role = 'owner' WHERE role = 'admin'")
        op.execute(f"UPDATE {table} SET role = 'member' WHERE role = 'individual'")
    op.execute("CREATE TYPE role AS ENUM ('owner', 'manager', 'member', 'admin')")
    for table in ROLE_TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN role TYPE role USING role::role")

    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.alter_column("users", "hashed_password", nullable=True)
    op.drop_column("users", "is_superuser")
    op.alter_column("users", "is_verified", new_column_name="email_verified")
