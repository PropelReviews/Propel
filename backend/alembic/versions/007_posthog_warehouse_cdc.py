"""PostHog data-warehouse CDC role and publication.

Revision ID: 007
Revises: 006
Create Date: 2026-06-17

Creates the dedicated PostHog Postgres login when POSTHOG_WAREHOUSE_DB_PASSWORD is
set (injected from Secrets Manager on ECS). Skipped in local dev and CI when unset.

Self-managed CDC: the publication is created here once for tables in ``public``
only (PostHog is granted SELECT on that schema); PostHog connects with a user
that has SELECT + REPLICATION (rds_replication on Aurora).
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POSTHOG_ROLE = "posthog"
POSTHOG_PUBLICATION = "posthog"


def _quote_ident(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        msg = f"unsafe SQL identifier: {name!r}"
        raise ValueError(msg)
    return f'"{name}"'


def _quote_literal(value: str) -> str:
    # Postgres utility statements (CREATE/ALTER ROLE PASSWORD) do not accept bind
    # parameters; escape single quotes in the secret instead.
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    password = os.environ.get("POSTHOG_WAREHOUSE_DB_PASSWORD")
    if not password:
        return

    conn = op.get_bind()
    db_name = conn.execute(sa.text("SELECT current_database()")).scalar_one()
    password_sql = _quote_literal(password)

    role_exists = (
        conn.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
            {"role": POSTHOG_ROLE},
        ).scalar()
        is not None
    )
    if role_exists:
        conn.execute(
            sa.text(
                f"ALTER ROLE {_quote_ident(POSTHOG_ROLE)} WITH PASSWORD {password_sql}"
            )
        )
    else:
        conn.execute(
            sa.text(
                f"CREATE ROLE {_quote_ident(POSTHOG_ROLE)} "
                f"WITH LOGIN PASSWORD {password_sql}"
            )
        )

    if (
        conn.execute(
            sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'rds_replication'")
        ).scalar()
        is not None
    ):
        conn.execute(sa.text(f"GRANT rds_replication TO {_quote_ident(POSTHOG_ROLE)}"))
    else:
        conn.execute(
            sa.text(f"ALTER ROLE {_quote_ident(POSTHOG_ROLE)} WITH REPLICATION")
        )

    conn.execute(
        sa.text(
            f"GRANT CONNECT ON DATABASE {_quote_ident(db_name)} "
            f"TO {_quote_ident(POSTHOG_ROLE)}"
        )
    )
    conn.execute(
        sa.text(f"GRANT USAGE ON SCHEMA public TO {_quote_ident(POSTHOG_ROLE)}")
    )
    conn.execute(
        sa.text(
            f"GRANT SELECT ON ALL TABLES IN SCHEMA public "
            f"TO {_quote_ident(POSTHOG_ROLE)}"
        )
    )
    conn.execute(
        sa.text(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT ON TABLES TO {_quote_ident(POSTHOG_ROLE)}"
        )
    )

    pub_exists = (
        conn.execute(
            sa.text("SELECT 1 FROM pg_publication WHERE pubname = :pub"),
            {"pub": POSTHOG_PUBLICATION},
        ).scalar()
        is not None
    )
    if not pub_exists:
        # Only public: PostHog is granted SELECT there, and publishing other
        # schemas (analytics/dagster) breaks delete+insert dbt marts that lack
        # a replica identity. See migration 012 for existing ALL TABLES pubs.
        conn.execute(
            sa.text(
                f"CREATE PUBLICATION {_quote_ident(POSTHOG_PUBLICATION)} "
                f"FOR TABLES IN SCHEMA public"
            )
        )


def downgrade() -> None:
    password = os.environ.get("POSTHOG_WAREHOUSE_DB_PASSWORD")
    if not password:
        return

    conn = op.get_bind()
    conn.execute(
        sa.text(f"DROP PUBLICATION IF EXISTS {_quote_ident(POSTHOG_PUBLICATION)}")
    )
    conn.execute(sa.text(f"DROP ROLE IF EXISTS {_quote_ident(POSTHOG_ROLE)}"))
