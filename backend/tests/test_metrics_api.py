"""Metrics API tests.

The endpoints read dbt-built analytics marts. The test DB never runs dbt, so
fixtures create and seed the tables directly with the schemas the dbt models
produce.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from tests.conftest import (
    auth_headers,
    create_tenant,
    login_user,
    register_user,
)

from app.db.session import async_session_maker


@pytest.fixture
async def analytics_tables(db_engine):
    """Create empty DORA primitive marts, dropped after the test."""
    async with db_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_pr_activity_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "prs_opened int NOT NULL, "
                "prs_merged int NOT NULL, "
                "prs_closed int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_pr_cycle_time_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "prs_merged int NOT NULL, "
                "median_cycle_time_hours float8 NOT NULL, "
                "avg_cycle_time_hours float8 NOT NULL, "
                "p90_cycle_time_hours float8 NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_review_latency_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "prs_first_reviewed int NOT NULL, "
                "median_time_to_first_review_hours float8, "
                "reviews_submitted int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_change_failure_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "prs_merged int NOT NULL, "
                "prs_reverted int NOT NULL, "
                "change_failure_rate float8 NOT NULL)"
            )
        )
        for table in (
            "fct_pr_activity_daily",
            "fct_pr_cycle_time_daily",
            "fct_review_latency_daily",
            "fct_change_failure_daily",
        ):
            await conn.execute(text(f"TRUNCATE analytics.{table}"))
    yield
    async with db_engine.begin() as conn:
        for table in (
            "fct_pr_activity_daily",
            "fct_pr_cycle_time_daily",
            "fct_review_latency_daily",
            "fct_change_failure_daily",
        ):
            await conn.execute(text(f"DROP TABLE IF EXISTS analytics.{table}"))
        await conn.execute(text("DROP SCHEMA IF EXISTS analytics"))


async def _seed_activity(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    opened: int = 0,
    merged: int = 0,
    closed: int = 0,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_pr_activity_daily "
                "(tenant_id, activity_date, prs_opened, prs_merged, prs_closed) "
                "VALUES (:tenant_id, :activity_date, :opened, :merged, :closed)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "opened": opened,
                "merged": merged,
                "closed": closed,
            },
        )
        await session.commit()


async def _seed_cycle_time(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    prs_merged: int,
    median: float,
    avg: float,
    p90: float,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_pr_cycle_time_daily "
                "(tenant_id, activity_date, prs_merged, "
                " median_cycle_time_hours, avg_cycle_time_hours, p90_cycle_time_hours) "
                "VALUES (:tenant_id, :activity_date, :prs_merged, :median, :avg, :p90)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "prs_merged": prs_merged,
                "median": median,
                "avg": avg,
                "p90": p90,
            },
        )
        await session.commit()


async def _seed_review_latency(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    prs_first_reviewed: int = 0,
    median_hours: float | None = None,
    reviews_submitted: int = 0,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_review_latency_daily "
                "(tenant_id, activity_date, prs_first_reviewed, "
                " median_time_to_first_review_hours, reviews_submitted) "
                "VALUES (:tenant_id, :activity_date, :prs_first_reviewed, "
                " :median_hours, :reviews_submitted)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "prs_first_reviewed": prs_first_reviewed,
                "median_hours": median_hours,
                "reviews_submitted": reviews_submitted,
            },
        )
        await session.commit()


async def _seed_change_failure(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    prs_merged: int,
    prs_reverted: int,
) -> None:
    rate = prs_reverted / prs_merged if prs_merged else 0.0
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_change_failure_daily "
                "(tenant_id, activity_date, prs_merged, prs_reverted, "
                " change_failure_rate) "
                "VALUES (:tenant_id, :activity_date, :prs_merged, :prs_reverted, :rate)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "prs_merged": prs_merged,
                "prs_reverted": prs_reverted,
                "rate": rate,
            },
        )
        await session.commit()


async def _setup_tenant(client: AsyncClient, email: str = "admin@example.com"):
    await register_user(client, email)
    token = await login_user(client, email)
    tenant = await create_tenant(client, token)
    return token, tenant


@pytest.mark.asyncio
async def test_pr_activity_daily(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_activity(tenant_id, date(2026, 6, 1), opened=3, merged=1)
    await _seed_activity(tenant_id, date(2026, 6, 2), opened=1, merged=2, closed=1)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-30"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["granularity"] == "daily"
    assert body["points"] == [
        {"period_start": "2026-06-01", "opened": 3, "merged": 1, "closed": 0},
        {"period_start": "2026-06-02", "opened": 1, "merged": 2, "closed": 1},
    ]


@pytest.mark.asyncio
async def test_pr_activity_weekly_and_monthly_bucketing(
    client: AsyncClient, analytics_tables
):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    # 2026-06-01 is a Monday; 2026-06-03 falls in the same ISO week,
    # 2026-06-08 in the next one. July dates roll into the next month bucket.
    await _seed_activity(tenant_id, date(2026, 6, 1), opened=2)
    await _seed_activity(tenant_id, date(2026, 6, 3), opened=1, merged=1)
    await _seed_activity(tenant_id, date(2026, 6, 8), closed=1)
    await _seed_activity(tenant_id, date(2026, 7, 1), merged=4)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"granularity": "weekly", "start": "2026-06-01", "end": "2026-07-31"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "opened": 3, "merged": 1, "closed": 0},
        {"period_start": "2026-06-08", "opened": 0, "merged": 0, "closed": 1},
        {"period_start": "2026-06-29", "opened": 0, "merged": 4, "closed": 0},
    ]

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"granularity": "monthly", "start": "2026-06-01", "end": "2026-07-31"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "opened": 3, "merged": 1, "closed": 1},
        {"period_start": "2026-07-01", "opened": 0, "merged": 4, "closed": 0},
    ]


@pytest.mark.asyncio
async def test_pr_activity_respects_date_range(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_activity(tenant_id, date(2026, 5, 31), opened=5)
    await _seed_activity(tenant_id, date(2026, 6, 1), opened=1)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-30"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["period_start"] == "2026-06-01"


@pytest.mark.asyncio
async def test_pr_activity_tenant_isolation(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client)

    # Another tenant's data must never leak into this tenant's series.
    await _seed_activity(uuid.uuid4(), date(2026, 6, 1), opened=9)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == []

    # Non-members get 404 (never reveal a tenant's existence).
    await register_user(client, "outsider@example.com")
    outsider_token = await login_user(client, "outsider@example.com")
    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        headers=auth_headers(outsider_token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_pr_activity_missing_table_returns_empty(client: AsyncClient):
    # No analytics_tables fixture: the dbt mart does not exist yet.
    token, tenant = await _setup_tenant(client)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"granularity": "daily", "points": []}


@pytest.mark.asyncio
async def test_pr_activity_invalid_range_rejected(
    client: AsyncClient, analytics_tables
):
    token, tenant = await _setup_tenant(client)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"start": "2026-06-30", "end": "2026-06-01"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_cycle_time_weighted_weekly(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    # Same ISO week (Mon 2026-06-01): weight medians by prs_merged.
    await _seed_cycle_time(
        tenant_id, date(2026, 6, 1), prs_merged=1, median=10, avg=10, p90=10
    )
    await _seed_cycle_time(
        tenant_id, date(2026, 6, 2), prs_merged=3, median=20, avg=22, p90=30
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/cycle-time",
        params={"granularity": "weekly", "start": "2026-06-01", "end": "2026-06-30"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["period_start"] == "2026-06-01"
    assert points[0]["prs_merged"] == 4
    assert points[0]["median_hours"] == pytest.approx((10 * 1 + 20 * 3) / 4)
    assert points[0]["avg_hours"] == pytest.approx((10 * 1 + 22 * 3) / 4)
    assert points[0]["p90_hours"] == pytest.approx((10 * 1 + 30 * 3) / 4)


@pytest.mark.asyncio
async def test_review_latency_and_change_failure(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_review_latency(
        tenant_id,
        date(2026, 6, 1),
        prs_first_reviewed=2,
        median_hours=4.5,
        reviews_submitted=5,
    )
    await _seed_change_failure(
        tenant_id, date(2026, 6, 1), prs_merged=4, prs_reverted=1
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/review-latency",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-01"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {
            "period_start": "2026-06-01",
            "prs_first_reviewed": 2,
            "median_hours_to_first_review": 4.5,
            "reviews_submitted": 5,
        }
    ]

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/change-failure",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-01"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["prs_merged"] == 4
    assert points[0]["prs_reverted"] == 1
    assert points[0]["change_failure_rate"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_dora_endpoints_missing_tables_return_empty(client: AsyncClient):
    token, tenant = await _setup_tenant(client, email="empty@example.com")
    headers = auth_headers(token)

    for path in ("cycle-time", "review-latency", "change-failure"):
        resp = await client.get(
            f"/api/v1/tenants/{tenant['id']}/metrics/{path}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"granularity": "daily", "points": []}
