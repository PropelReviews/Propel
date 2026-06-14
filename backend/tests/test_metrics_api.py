"""Metrics API tests.

The endpoint reads the dbt-built `analytics.fct_pr_activity_daily` mart. The
test DB never runs dbt, so a fixture creates and seeds the table directly with
the exact schema the dbt model produces.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from tests.conftest import (
    act_as_headers,
    create_tenant,
    login_test_user,
    login_user,
)

from app.db.session import async_session_maker


@pytest.fixture
async def analytics_table(db_engine):
    """Create an empty analytics.fct_pr_activity_daily, dropped after the test."""
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
        await conn.execute(text("TRUNCATE analytics.fct_pr_activity_daily"))
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS analytics.fct_pr_activity_daily"))
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


async def _setup_tenant(client: AsyncClient, email: str = "admin@example.com"):
    await login_test_user(client, email)
    token = await login_user(client, email)
    tenant = await create_tenant(client, token)
    return token, tenant


@pytest.mark.asyncio
async def test_pr_activity_daily(client: AsyncClient, analytics_table):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_activity(tenant_id, date(2026, 6, 1), opened=3, merged=1)
    await _seed_activity(tenant_id, date(2026, 6, 2), opened=1, merged=2, closed=1)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-30"},
        headers=act_as_headers(token),
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
    client: AsyncClient, analytics_table
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
        headers=act_as_headers(token),
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
        headers=act_as_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "opened": 3, "merged": 1, "closed": 1},
        {"period_start": "2026-07-01", "opened": 0, "merged": 4, "closed": 0},
    ]


@pytest.mark.asyncio
async def test_pr_activity_respects_date_range(client: AsyncClient, analytics_table):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_activity(tenant_id, date(2026, 5, 31), opened=5)
    await _seed_activity(tenant_id, date(2026, 6, 1), opened=1)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-30"},
        headers=act_as_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["period_start"] == "2026-06-01"


@pytest.mark.asyncio
async def test_pr_activity_tenant_isolation(client: AsyncClient, analytics_table):
    token, tenant = await _setup_tenant(client)

    # Another tenant's data must never leak into this tenant's series.
    await _seed_activity(uuid.uuid4(), date(2026, 6, 1), opened=9)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        headers=act_as_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == []

    # Non-members get 404 (never reveal a tenant's existence).
    await login_test_user(client, "outsider@example.com")
    outsider_token = await login_user(client, "outsider@example.com")
    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        headers=act_as_headers(outsider_token),
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_pr_activity_missing_table_returns_empty(client: AsyncClient):
    # No analytics_table fixture: the dbt mart does not exist yet.
    token, tenant = await _setup_tenant(client)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        headers=act_as_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"granularity": "daily", "points": []}


@pytest.mark.asyncio
async def test_pr_activity_invalid_range_rejected(client: AsyncClient, analytics_table):
    token, tenant = await _setup_tenant(client)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"start": "2026-06-30", "end": "2026-06-01"},
        headers=act_as_headers(token),
    )
    assert resp.status_code == 422, resp.text
