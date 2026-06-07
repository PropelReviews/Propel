"""Process-wide psycopg connection for the target.

Reads PROPEL_DATABASE_URL (a sync postgresql:// URL) set by the orchestrator.
Autocommit keeps landing durable record-by-record for V1 volumes.
"""

from __future__ import annotations

import os

import psycopg

_connection: psycopg.Connection | None = None


def _normalize_dsn(url: str) -> str:
    # psycopg wants a sync driver URL; strip any asyncpg suffix defensively.
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def get_connection() -> psycopg.Connection:
    global _connection
    if _connection is None or _connection.closed:
        dsn = os.environ.get("PROPEL_DATABASE_URL")
        if not dsn:
            raise RuntimeError("PROPEL_DATABASE_URL is not set")
        _connection = psycopg.connect(_normalize_dsn(dsn), autocommit=True)
    return _connection
