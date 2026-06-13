#!/usr/bin/env python
"""Prepare Dagster's Postgres storage and print its connection URL.

Dagster shares the application's Postgres instance but keeps its run, event-log,
and schedule tables (and its own ``alembic_version``) in a dedicated ``dagster``
schema so they never collide with the app's Alembic migrations. This script
creates the schema if missing and prints a psycopg2 URL whose ``search_path``
points at it.

Optionally materializes ``orchestration/dagster.yaml`` into ``$DAGSTER_HOME`` with
the connection URL inlined so Dagster subprocesses do not depend on
``DAGSTER_PG_URL`` staying in the environment.

Status messages go to stderr; only the URL is written to stdout so callers can::

    export DAGSTER_PG_URL="$(python prepare_dagster_db.py)"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

SCHEMA = "dagster"
_ENV_POSTGRES_URL_MARKER = "postgres_url:\n      env: DAGSTER_PG_URL"


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


def _default_template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "dagster.yaml"


def materialize_dagster_yaml(
    dagster_home: Path,
    postgres_url: str,
    template_path: Path | None = None,
) -> None:
    """Write dagster.yaml with an inlined Postgres URL (no env: lookup)."""
    template = (template_path or _default_template_path()).read_text()
    if _ENV_POSTGRES_URL_MARKER not in template:
        raise ValueError(
            "dagster.yaml template is missing the postgres_url env: DAGSTER_PG_URL marker"
        )
    escaped_url = postgres_url.replace("\\", "\\\\").replace('"', '\\"')
    dagster_home.mkdir(parents=True, exist_ok=True)
    (dagster_home / "dagster.yaml").write_text(
        template.replace(
            _ENV_POSTGRES_URL_MARKER,
            f'postgres_url: "{escaped_url}"',
        )
    )


def prepare_postgres_url() -> str | None:
    """Create the dagster schema and return the schema-scoped connection URL."""
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        print("DATABASE_URL is not set", file=sys.stderr)
        return None

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

    return _with_search_path(base_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Dagster Postgres storage")
    parser.add_argument(
        "--dagster-home",
        metavar="DIR",
        help="Materialize orchestration/dagster.yaml into DIR with an inlined Postgres URL",
    )
    parser.add_argument(
        "--template",
        metavar="PATH",
        help="dagster.yaml template (default: orchestration/dagster.yaml next to this script)",
    )
    args = parser.parse_args()

    postgres_url = prepare_postgres_url()
    if postgres_url is None:
        return 1

    if args.dagster_home:
        template_path = Path(args.template) if args.template else None
        try:
            materialize_dagster_yaml(
                Path(args.dagster_home),
                postgres_url,
                template_path=template_path,
            )
        except (OSError, ValueError) as exc:
            print(f"Failed to write Dagster instance config: {exc}", file=sys.stderr)
            return 1

    print(postgres_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
