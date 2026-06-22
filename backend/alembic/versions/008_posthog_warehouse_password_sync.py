"""Re-sync PostHog warehouse role password and publication.

Revision ID: 008
Revises: 007
Create Date: 2026-06-17

007 may have been stamped before POSTHOG_WAREHOUSE_DB_PASSWORD was injected, leaving
no role or a stale password. This revision idempotently creates/updates the role
whenever the env var is present.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
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
        conn.execute(
            sa.text(
                f"CREATE PUBLICATION {_quote_ident(POSTHOG_PUBLICATION)} FOR ALL TABLES"
            )
        )


def downgrade() -> None:
    pass
