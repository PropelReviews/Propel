"""Datapoint idempotency at the DB layer (ingestion spec §6).

Exercises the same partial-index ON CONFLICT clauses target-propel relies on,
through the app's async engine, so the dedup/restatement contract is covered by
the backend suite regardless of the target's own (psycopg) test setup.
"""

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db.session import async_session_maker

_EVENT_INSERT = text(
    """
    INSERT INTO datapoint
        (id, tenant_id, source, tool, kind, name, subject_type, subject_id,
         occurred_at, source_key, metadata)
    VALUES
        (:id, :tenant_id, 'github', 'github', 'event', 'pull_request', 'user',
         'octocat', :occurred_at, :source_key, cast(:metadata as jsonb))
    ON CONFLICT (tenant_id, source, source_key) WHERE kind = 'event'
    DO NOTHING
    """
)

_MEASURE_UPSERT = text(
    """
    INSERT INTO datapoint
        (id, tenant_id, source, tool, kind, name, subject_type, subject_id,
         occurred_at, period_start, period_end, source_key, metadata, observed_at)
    VALUES
        (:id, :tenant_id, 'github', 'github_copilot', 'measurement',
         'copilot.usage', 'user', 'octocat', :period_start, :period_start,
         :period_end, :source_key, cast(:metadata as jsonb), :observed_at)
    ON CONFLICT (tenant_id, tool, name, subject_id, period_start)
        WHERE kind = 'measurement'
    DO UPDATE SET observed_at = EXCLUDED.observed_at, metadata = EXCLUDED.metadata
    WHERE datapoint.observed_at < EXCLUDED.observed_at
    """
)


@pytest.mark.asyncio
async def test_event_conflict_does_nothing(clean_db):
    tenant_id = uuid.uuid4()
    params = {
        "tenant_id": tenant_id,
        "occurred_at": datetime(2026, 6, 1, tzinfo=UTC),
        "source_key": "node_PR_1",
        "metadata": json.dumps({}),
    }
    async with async_session_maker() as session:
        for _ in range(2):
            await session.execute(_EVENT_INSERT, {"id": uuid.uuid4(), **params})
        await session.commit()
        count = await session.scalar(
            text(
                "SELECT count(*) FROM datapoint WHERE tenant_id = :t AND kind = 'event'"
            ),
            {"t": tenant_id},
        )
    assert count == 1


@pytest.mark.asyncio
async def test_measurement_newest_observed_at_wins(clean_db):
    tenant_id = uuid.uuid4()
    base = {
        "tenant_id": tenant_id,
        "period_start": datetime(2026, 6, 1, tzinfo=UTC),
        "period_end": datetime(2026, 6, 2, tzinfo=UTC),
        "source_key": "octocat:2026-06-01",
    }
    async with async_session_maker() as session:
        # initial
        await session.execute(
            _MEASURE_UPSERT,
            {
                "id": uuid.uuid4(),
                "metadata": json.dumps({"v": 1}),
                "observed_at": datetime(2026, 6, 2, tzinfo=UTC),
                **base,
            },
        )
        # newer observed_at -> updates
        await session.execute(
            _MEASURE_UPSERT,
            {
                "id": uuid.uuid4(),
                "metadata": json.dumps({"v": 2}),
                "observed_at": datetime(2026, 6, 3, tzinfo=UTC),
                **base,
            },
        )
        # older observed_at -> ignored
        await session.execute(
            _MEASURE_UPSERT,
            {
                "id": uuid.uuid4(),
                "metadata": json.dumps({"v": 99}),
                "observed_at": datetime(2026, 6, 1, tzinfo=UTC),
                **base,
            },
        )
        await session.commit()

        rows = await session.scalar(
            text(
                "SELECT count(*) FROM datapoint "
                "WHERE tenant_id = :t AND kind = 'measurement'"
            ),
            {"t": tenant_id},
        )
        final = await session.scalar(
            text(
                "SELECT metadata->>'v' FROM datapoint "
                "WHERE tenant_id = :t AND kind = 'measurement'"
            ),
            {"t": tenant_id},
        )
    assert rows == 1
    assert final == "2"
