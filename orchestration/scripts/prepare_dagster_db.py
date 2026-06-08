#!/usr/bin/env python
"""Prepare Dagster's Postgres storage and print its connection URL.

Dagster shares the application's Postgres instance but keeps its run, event-log,
and schedule tables (and its own ``alembic_version``) in a dedicated ``dagster``
schema so they never collide with the app's Alembic migrations. This script
creates the schema if missing and prints a psycopg2 URL whose ``search_path``
points at it.

Status messages go to stderr; only the URL is written to stdout so callers can::

    export DAGSTER_PG_URL="$(python prepare_dagster_db.py)"
"""

from __future__ import annotations

import os
import sys
from urllib.parse import quote, urlsplit, urlunsplit

SCHEMA = "dagster"


def _sync_url(raw: str) -> str:
    """Return a psycopg2-compatible (sync) URL, dropping any async driver."""
    for prefix in ("postgresql+asyncpg://", "postgres://"):
        if raw.startswith(prefix):
            return "postgresql://" + raw[len(prefix) :]
    return raw


def _with_search_path(url: str) -> str:
    """Append a libpq ``options`` param pinning the schema search_path."""
    parts = urlsplit(url)
    option = quote(f"-csearch_path={SCHEMA}")
    extra = f"options={option}"
    new_query = f"{parts.query}&{extra}" if parts.query else extra
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def main() -> int:
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    base_url = _sync_url(raw)

    import psycopg2

    conn = psycopg2.connect(base_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    finally:
        conn.close()
    print(f"Ensured Dagster schema '{SCHEMA}' exists", file=sys.stderr)

    print(_with_search_path(base_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
