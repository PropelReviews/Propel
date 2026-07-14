"""Postgres swap isolation: readers never see mixed definition_version rows."""

from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_swap_under_repeatable_read_sees_single_version(db_engine):
    """Simulate M4 swap: open RR cursor, swap rows, cursor stays consistent."""
    async with db_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS analytics.fct_metric_values (
                    tenant_id uuid NOT NULL,
                    metric_id text NOT NULL,
                    definition_version text NOT NULL,
                    grain text NOT NULL,
                    bucket_start timestamptz NOT NULL,
                    value float8
                )
                """
            )
        )
        await conn.execute(text("TRUNCATE analytics.fct_metric_values"))
        await conn.execute(
            text(
                """
                INSERT INTO analytics.fct_metric_values
                VALUES
                  ('00000000-0000-0000-0000-000000000001'::uuid,
                   'propel.merged_prs', '1', 'day',
                   '2026-01-01'::timestamptz, 10),
                  ('00000000-0000-0000-0000-000000000001'::uuid,
                   'propel.merged_prs', '1', 'day',
                   '2026-01-02'::timestamptz, 20)
                """
            )
        )

    async with db_engine.connect() as rconn:
        await rconn.execute(text("BEGIN ISOLATION LEVEL REPEATABLE READ"))
        result = await rconn.execute(
            text(
                "SELECT DISTINCT definition_version "
                "FROM analytics.fct_metric_values "
                "WHERE metric_id = 'propel.merged_prs'"
            )
        )
        versions_before = {row[0] for row in result}

        async with db_engine.begin() as wconn:
            await wconn.execute(
                text(
                    "DELETE FROM analytics.fct_metric_values "
                    "WHERE metric_id = 'propel.merged_prs'"
                )
            )
            await wconn.execute(
                text(
                    """
                    INSERT INTO analytics.fct_metric_values
                    VALUES
                      ('00000000-0000-0000-0000-000000000001'::uuid,
                       'propel.merged_prs', '2', 'day',
                       '2026-01-01'::timestamptz, 11),
                      ('00000000-0000-0000-0000-000000000001'::uuid,
                       'propel.merged_prs', '2', 'day',
                       '2026-01-02'::timestamptz, 22)
                    """
                )
            )

        result2 = await rconn.execute(
            text(
                "SELECT DISTINCT definition_version "
                "FROM analytics.fct_metric_values "
                "WHERE metric_id = 'propel.merged_prs'"
            )
        )
        versions_during = {row[0] for row in result2}
        await rconn.execute(text("COMMIT"))

    assert versions_before == {"1"}
    # REPEATABLE READ snapshot must not observe the post-swap version.
    assert versions_during == {"1"}

    async with db_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT DISTINCT definition_version "
                    "FROM analytics.fct_metric_values "
                    "WHERE metric_id = 'propel.merged_prs'"
                )
            )
        ).fetchall()
    assert {r[0] for r in rows} == {"2"}

    # Do not leave analytics objects around for other suites' DROP SCHEMA.
    async with db_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS analytics.fct_metric_values"))
