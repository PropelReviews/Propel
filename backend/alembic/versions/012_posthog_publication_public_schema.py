"""Narrow PostHog publication to the public schema.

Revision ID: 012
Revises: 011
Create Date: 2026-07-13

007/008 created ``CREATE PUBLICATION posthog FOR ALL TABLES``, which auto-includes
every schema — including dbt ``analytics`` marts and Dagster metadata. Incremental
dbt models use delete+insert; Postgres then refuses DELETEs on published tables
that lack a replica identity:

    cannot delete from table "fct_tickets" because it does not have a replica
    identity and publishes deletes

PostHog is only granted SELECT on ``public`` (see 007/008), so publishing other
schemas was never intentional. Rebuild the publication as
``FOR TABLES IN SCHEMA public`` when the warehouse password is present.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POSTHOG_PUBLICATION = "posthog"
PUBLIC_SCHEMA = "public"


def _quote_ident(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        msg = f"unsafe SQL identifier: {name!r}"
        raise ValueError(msg)
    return f'"{name}"'


def _create_public_schema_publication(conn: sa.Connection) -> None:
    conn.execute(
        sa.text(
            f"CREATE PUBLICATION {_quote_ident(POSTHOG_PUBLICATION)} "
            f"FOR TABLES IN SCHEMA {_quote_ident(PUBLIC_SCHEMA)}"
        )
    )


def upgrade() -> None:
    password = os.environ.get("POSTHOG_WAREHOUSE_DB_PASSWORD")
    if not password:
        return

    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT puballtables FROM pg_publication WHERE pubname = :pub"),
        {"pub": POSTHOG_PUBLICATION},
    ).one_or_none()

    if row is None:
        _create_public_schema_publication(conn)
        return

    if not row.puballtables:
        # Already schema-scoped (or table-list); leave it alone.
        return

    # FOR ALL TABLES cannot be altered in place — recreate narrowed.
    conn.execute(sa.text(f"DROP PUBLICATION {_quote_ident(POSTHOG_PUBLICATION)}"))
    _create_public_schema_publication(conn)


def downgrade() -> None:
    password = os.environ.get("POSTHOG_WAREHOUSE_DB_PASSWORD")
    if not password:
        return

    conn = op.get_bind()
    pub_exists = (
        conn.execute(
            sa.text("SELECT 1 FROM pg_publication WHERE pubname = :pub"),
            {"pub": POSTHOG_PUBLICATION},
        ).scalar()
        is not None
    )
    if not pub_exists:
        return

    conn.execute(sa.text(f"DROP PUBLICATION {_quote_ident(POSTHOG_PUBLICATION)}"))
    conn.execute(
        sa.text(
            f"CREATE PUBLICATION {_quote_ident(POSTHOG_PUBLICATION)} FOR ALL TABLES"
        )
    )
