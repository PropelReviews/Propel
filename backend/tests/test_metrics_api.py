"""Metrics API tests.

The endpoints read dbt-built analytics marts. The test DB never runs dbt, so
fixtures create and seed the tables directly with the schemas the dbt models
produce.

`scope=me` endpoints read `raw_record` (Alembic-owned, always present) instead
of the marts, so those tests seed raw GitHub payloads and a linked
ExternalIdentity rather than the analytics tables.
"""

import uuid
from datetime import UTC, date, datetime

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
from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    AuthType,
    GitHubOrgRole,
    IdentityStatus,
    IntegrationProvider,
)
from app.models.external_identity import ExternalIdentity
from app.models.raw_record import RawRecord


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
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_deployment_frequency_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "releases_published int NOT NULL, "
                "production_releases int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_review_comments_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "review_comments_created int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_workflow_runs_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "runs_started int NOT NULL, "
                "runs_completed int NOT NULL, "
                "runs_success int NOT NULL, "
                "runs_failure int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_ticket_activity_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "source text NOT NULL, "
                "tickets_created int NOT NULL, "
                "tickets_completed int NOT NULL, "
                "tickets_canceled int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_ticket_comments_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "source text NOT NULL, "
                "comments_created int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS analytics.fct_project_activity_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "source text NOT NULL, "
                "projects_created int NOT NULL, "
                "projects_completed int NOT NULL, "
                "projects_canceled int NOT NULL)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS "
                "analytics.fct_ticket_description_edits_daily ("
                "tenant_id uuid NOT NULL, "
                "activity_date date NOT NULL, "
                "source text NOT NULL, "
                "description_edits int NOT NULL)"
            )
        )
        for table in (
            "fct_pr_activity_daily",
            "fct_pr_cycle_time_daily",
            "fct_review_latency_daily",
            "fct_change_failure_daily",
            "fct_deployment_frequency_daily",
            "fct_review_comments_daily",
            "fct_workflow_runs_daily",
            "fct_ticket_activity_daily",
            "fct_ticket_comments_daily",
            "fct_project_activity_daily",
            "fct_ticket_description_edits_daily",
        ):
            await conn.execute(text(f"TRUNCATE analytics.{table}"))
    yield
    async with db_engine.begin() as conn:
        for table in (
            "fct_pr_activity_daily",
            "fct_pr_cycle_time_daily",
            "fct_review_latency_daily",
            "fct_change_failure_daily",
            "fct_deployment_frequency_daily",
            "fct_review_comments_daily",
            "fct_workflow_runs_daily",
            "fct_ticket_activity_daily",
            "fct_ticket_comments_daily",
            "fct_project_activity_daily",
            "fct_ticket_description_edits_daily",
        ):
            await conn.execute(text(f"DROP TABLE IF EXISTS analytics.{table}"))
        await conn.execute(text("DROP SCHEMA IF EXISTS analytics CASCADE"))


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


async def _seed_deployment_frequency(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    releases_published: int,
    production_releases: int,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_deployment_frequency_daily "
                "(tenant_id, activity_date, releases_published, production_releases) "
                "VALUES (:tenant_id, :activity_date, :releases_published, "
                " :production_releases)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "releases_published": releases_published,
                "production_releases": production_releases,
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
async def test_deployment_frequency(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_deployment_frequency(
        tenant_id, date(2026, 6, 1), releases_published=2, production_releases=1
    )
    await _seed_deployment_frequency(
        tenant_id, date(2026, 6, 2), releases_published=1, production_releases=1
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/deployment-frequency",
        params={"granularity": "weekly", "start": "2026-06-01", "end": "2026-06-30"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["period_start"] == "2026-06-01"
    assert points[0]["releases_published"] == 3
    assert points[0]["production_releases"] == 2


@pytest.mark.asyncio
async def test_dora_endpoints_missing_tables_return_empty(client: AsyncClient):
    token, tenant = await _setup_tenant(client, email="empty@example.com")
    headers = auth_headers(token)

    for path in (
        "cycle-time",
        "review-latency",
        "change-failure",
        "deployment-frequency",
        "review-comments",
        "workflow-runs",
        "tickets",
        "ticket-comments",
        "projects",
        "ticket-description-edits",
    ):
        resp = await client.get(
            f"/api/v1/tenants/{tenant['id']}/metrics/{path}",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"granularity": "daily", "points": []}


async def _seed_review_comments(
    tenant_id: uuid.UUID, activity_date: date, *, count: int
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_review_comments_daily "
                "(tenant_id, activity_date, review_comments_created) "
                "VALUES (:tenant_id, :activity_date, :count)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "count": count,
            },
        )
        await session.commit()


async def _seed_workflow_runs(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    started: int,
    completed: int,
    success: int,
    failure: int,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_workflow_runs_daily "
                "(tenant_id, activity_date, runs_started, runs_completed, "
                " runs_success, runs_failure) "
                "VALUES (:tenant_id, :activity_date, :started, :completed, "
                " :success, :failure)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "started": started,
                "completed": completed,
                "success": success,
                "failure": failure,
            },
        )
        await session.commit()


async def _seed_ticket_activity(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    source: str = "linear",
    created: int = 0,
    completed: int = 0,
    canceled: int = 0,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_ticket_activity_daily "
                "(tenant_id, activity_date, source, tickets_created, "
                " tickets_completed, tickets_canceled) "
                "VALUES (:tenant_id, :activity_date, :source, :created, "
                " :completed, :canceled)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "source": source,
                "created": created,
                "completed": completed,
                "canceled": canceled,
            },
        )
        await session.commit()


async def _seed_ticket_comments(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    source: str = "linear",
    count: int,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_ticket_comments_daily "
                "(tenant_id, activity_date, source, comments_created) "
                "VALUES (:tenant_id, :activity_date, :source, :count)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "source": source,
                "count": count,
            },
        )
        await session.commit()


async def _seed_project_activity(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    source: str = "linear",
    created: int = 0,
    completed: int = 0,
    canceled: int = 0,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_project_activity_daily "
                "(tenant_id, activity_date, source, projects_created, "
                " projects_completed, projects_canceled) "
                "VALUES (:tenant_id, :activity_date, :source, :created, "
                " :completed, :canceled)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "source": source,
                "created": created,
                "completed": completed,
                "canceled": canceled,
            },
        )
        await session.commit()


async def _seed_ticket_description_edits(
    tenant_id: uuid.UUID,
    activity_date: date,
    *,
    source: str = "linear",
    count: int,
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                "INSERT INTO analytics.fct_ticket_description_edits_daily "
                "(tenant_id, activity_date, source, description_edits) "
                "VALUES (:tenant_id, :activity_date, :source, :count)"
            ),
            {
                "tenant_id": tenant_id,
                "activity_date": activity_date,
                "source": source,
                "count": count,
            },
        )
        await session.commit()


@pytest.mark.asyncio
async def test_review_comments_and_workflow_runs(client: AsyncClient, analytics_tables):
    token, tenant = await _setup_tenant(client, email="primitives@example.com")
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_review_comments(tenant_id, date(2026, 6, 1), count=4)
    await _seed_workflow_runs(
        tenant_id,
        date(2026, 6, 1),
        started=5,
        completed=4,
        success=3,
        failure=1,
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/review-comments",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-01"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "review_comments_created": 4}
    ]

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/workflow-runs",
        params={"granularity": "daily", "start": "2026-06-01", "end": "2026-06-01"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {
            "period_start": "2026-06-01",
            "runs_started": 5,
            "runs_completed": 4,
            "runs_success": 3,
            "runs_failure": 1,
        }
    ]


@pytest.mark.asyncio
async def test_normalized_ticket_and_project_metrics(
    client: AsyncClient, analytics_tables
):
    token, tenant = await _setup_tenant(client, email="ticket-metrics@example.com")
    tenant_id = uuid.UUID(tenant["id"])
    headers = auth_headers(token)
    params = {"granularity": "daily", "start": "2026-06-01", "end": "2026-06-01"}

    # Two sources on the same day — API sums across source.
    await _seed_ticket_activity(
        tenant_id, date(2026, 6, 1), source="linear", created=2, completed=1
    )
    await _seed_ticket_activity(
        tenant_id, date(2026, 6, 1), source="github", created=1, canceled=1
    )
    await _seed_ticket_comments(tenant_id, date(2026, 6, 1), source="linear", count=4)
    await _seed_ticket_comments(tenant_id, date(2026, 6, 1), source="github", count=3)
    await _seed_project_activity(
        tenant_id, date(2026, 6, 1), created=1, completed=1, canceled=0
    )
    await _seed_ticket_description_edits(tenant_id, date(2026, 6, 1), count=2)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/tickets",
        params=params,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {
            "period_start": "2026-06-01",
            "tickets_created": 3,
            "tickets_completed": 1,
            "tickets_canceled": 1,
        }
    ]

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/ticket-comments",
        params=params,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "comments_created": 7}
    ]

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/projects",
        params=params,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {
            "period_start": "2026-06-01",
            "projects_created": 1,
            "projects_completed": 1,
            "projects_canceled": 0,
        }
    ]

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/ticket-description-edits",
        params=params,
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "description_edits": 2}
    ]


# --------------------------------------------------------------------------- #
# scope=me (person-scoped series from raw_record)
# --------------------------------------------------------------------------- #


async def _link_github_identity(
    tenant_id: uuid.UUID, user_id: uuid.UUID, login: str
) -> None:
    async with async_session_maker() as session:
        account = ConnectedAccount(
            tenant_id=tenant_id,
            provider=IntegrationProvider.github.value,
            auth_type=AuthType.github_app_installation.value,
            external_account_id="1",
            external_account_name="acme",
        )
        session.add(account)
        await session.flush()
        session.add(
            ExternalIdentity(
                tenant_id=tenant_id,
                connected_account_id=account.id,
                provider=IntegrationProvider.github.value,
                external_user_id="1001",
                external_login=login,
                propel_user_id=user_id,
                status=IdentityStatus.linked.value,
                github_org_role=GitHubOrgRole.member.value,
            )
        )
        await session.commit()


async def _seed_raw_pr(
    tenant_id: uuid.UUID,
    *,
    node_id: str,
    number: int,
    author: str,
    created_at: str,
    merged_at: str | None = None,
    closed_at: str | None = None,
    title: str = "Add feature",
    repo: str = "acme/app",
    fetched_at: datetime | None = None,
) -> None:
    async with async_session_maker() as session:
        session.add(
            RawRecord(
                tenant_id=tenant_id,
                source="github",
                resource_type="pull_requests",
                source_id=node_id,
                payload={
                    "node_id": node_id,
                    "number": number,
                    "title": title,
                    "state": "closed" if (merged_at or closed_at) else "open",
                    "created_at": created_at,
                    "merged_at": merged_at,
                    "closed_at": closed_at or merged_at,
                    "user": {"login": author},
                    "base": {"repo": {"full_name": repo}},
                },
                fetched_at=fetched_at or datetime.now(UTC),
            )
        )
        await session.commit()


async def _seed_raw_review(
    tenant_id: uuid.UUID,
    *,
    node_id: str,
    pr_number: int,
    reviewer: str,
    submitted_at: str,
    org: str = "acme",
    repo: str = "app",
    state: str = "APPROVED",
) -> None:
    async with async_session_maker() as session:
        session.add(
            RawRecord(
                tenant_id=tenant_id,
                source="github",
                resource_type="reviews",
                source_id=node_id,
                payload={
                    "node_id": node_id,
                    "id": 1,
                    "state": state,
                    "submitted_at": submitted_at,
                    "user": {"login": reviewer},
                    "pull_request_number": pr_number,
                    "org": org,
                    "repo": repo,
                },
            )
        )
        await session.commit()


async def _setup_linked_tenant(client: AsyncClient, *, login: str = "alice"):
    user = await register_user(client, "ic@example.com")
    token = await login_user(client, "ic@example.com")
    tenant = await create_tenant(client, token)
    await _link_github_identity(uuid.UUID(tenant["id"]), uuid.UUID(user["id"]), login)
    return token, tenant


@pytest.mark.asyncio
async def test_scope_me_pr_activity_filters_to_caller(client: AsyncClient):
    token, tenant = await _setup_linked_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-02T10:00:00Z",
    )
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_2",
        number=2,
        author="bob",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-01T18:00:00Z",
    )
    # Another tenant's PR by the same login never leaks in.
    await _seed_raw_pr(
        uuid.uuid4(),
        node_id="PR_3",
        number=3,
        author="alice",
        created_at="2026-06-01T09:00:00Z",
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={
            "granularity": "daily",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "scope": "me",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "opened": 1, "merged": 0, "closed": 0},
        {"period_start": "2026-06-02", "opened": 0, "merged": 1, "closed": 0},
    ]


@pytest.mark.asyncio
async def test_scope_me_uses_latest_pr_snapshot(client: AsyncClient):
    token, tenant = await _setup_linked_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    # First sync: open PR. Later re-sync: same PR now merged. Only the newest
    # snapshot counts, so the PR contributes one open + one merge, not two opens.
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
        fetched_at=datetime(2026, 6, 1, 11, tzinfo=UTC),
    )
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-03T10:00:00Z",
        fetched_at=datetime(2026, 6, 3, 11, tzinfo=UTC),
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={
            "granularity": "daily",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "scope": "me",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["points"] == [
        {"period_start": "2026-06-01", "opened": 1, "merged": 0, "closed": 0},
        {"period_start": "2026-06-03", "opened": 0, "merged": 1, "closed": 0},
    ]


@pytest.mark.asyncio
async def test_scope_me_cycle_time_true_percentiles(client: AsyncClient):
    token, tenant = await _setup_linked_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    # Two merges in the same week: 24h and 48h cycle times.
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-02T10:00:00Z",
    )
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_2",
        number=2,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-03T10:00:00Z",
    )
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_3",
        number=3,
        author="bob",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-05T10:00:00Z",
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/cycle-time",
        params={
            "granularity": "weekly",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "scope": "me",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["prs_merged"] == 2
    assert points[0]["median_hours"] == pytest.approx(36.0)
    assert points[0]["avg_hours"] == pytest.approx(36.0)


@pytest.mark.asyncio
async def test_scope_me_review_latency_and_change_failure(client: AsyncClient):
    token, tenant = await _setup_linked_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-02T10:00:00Z",
        title="Revert: broken change",
    )
    # First review 6h after open; a later review the same week.
    await _seed_raw_review(
        tenant_id,
        node_id="REV_1",
        pr_number=1,
        reviewer="bob",
        submitted_at="2026-06-01T16:00:00Z",
    )
    await _seed_raw_review(
        tenant_id,
        node_id="REV_2",
        pr_number=1,
        reviewer="carol",
        submitted_at="2026-06-02T08:00:00Z",
    )
    # Alice's self-review never counts toward her own latency.
    await _seed_raw_review(
        tenant_id,
        node_id="REV_3",
        pr_number=1,
        reviewer="alice",
        submitted_at="2026-06-01T11:00:00Z",
    )
    # Bob's PR + its review are invisible in alice's scope.
    await _seed_raw_pr(
        tenant_id,
        node_id="PR_2",
        number=2,
        author="bob",
        created_at="2026-06-01T10:00:00Z",
        merged_at="2026-06-02T10:00:00Z",
    )
    await _seed_raw_review(
        tenant_id,
        node_id="REV_4",
        pr_number=2,
        reviewer="alice",
        submitted_at="2026-06-01T12:00:00Z",
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/review-latency",
        params={
            "granularity": "weekly",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "scope": "me",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["prs_first_reviewed"] == 1
    assert points[0]["median_hours_to_first_review"] == pytest.approx(6.0)
    assert points[0]["reviews_submitted"] == 2

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/change-failure",
        params={
            "granularity": "weekly",
            "start": "2026-06-01",
            "end": "2026-06-30",
            "scope": "me",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["prs_merged"] == 1
    assert points[0]["prs_reverted"] == 1
    assert points[0]["change_failure_rate"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_scope_me_unlinked_user_gets_empty_series(client: AsyncClient):
    # No ExternalIdentity for this user: series must be empty, not org-wide.
    token, tenant = await _setup_tenant(client, email="unlinked-ic@example.com")
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="someone",
        created_at="2026-06-01T10:00:00Z",
    )

    for path in ("pull-requests", "cycle-time", "review-latency", "change-failure"):
        resp = await client.get(
            f"/api/v1/tenants/{tenant['id']}/metrics/{path}",
            params={"scope": "me"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["points"] == []


@pytest.mark.asyncio
async def test_scope_org_ignores_raw_records(client: AsyncClient, analytics_tables):
    # scope=org (and the default) still reads the marts, not raw_record.
    token, tenant = await _setup_linked_tenant(client)
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_raw_pr(
        tenant_id,
        node_id="PR_1",
        number=1,
        author="alice",
        created_at="2026-06-01T10:00:00Z",
    )
    await _seed_activity(tenant_id, date(2026, 6, 5), opened=7)

    for params in ({}, {"scope": "org"}):
        resp = await client.get(
            f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
            params={"start": "2026-06-01", "end": "2026-06-30", **params},
            headers=auth_headers(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["points"] == [
            {"period_start": "2026-06-05", "opened": 7, "merged": 0, "closed": 0}
        ]


@pytest.mark.asyncio
async def test_scope_rejects_arbitrary_values(client: AsyncClient):
    # Clients can never request another user's series by name.
    token, tenant = await _setup_tenant(client, email="snoop@example.com")
    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/pull-requests",
        params={"scope": "bob"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


@pytest.fixture
async def fct_metric_values_table(db_engine):
    """Create analytics.fct_metric_values with the is_total serving contract."""
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
                    bucket_end timestamptz,
                    is_complete boolean,
                    is_total boolean NOT NULL DEFAULT true,
                    dim_repo text NOT NULL DEFAULT '',
                    dim_team text NOT NULL DEFAULT '',
                    value float8,
                    numerator float8,
                    denominator float8
                )
                """
            )
        )
        await conn.execute(text("TRUNCATE analytics.fct_metric_values"))
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS analytics.fct_metric_values"))


async def _seed_metric_value(
    tenant_id: uuid.UUID,
    *,
    metric_id: str,
    grain: str,
    bucket_start: datetime,
    value: float | None,
    is_total: bool = True,
    dim_repo: str = "",
) -> None:
    async with async_session_maker() as session:
        await session.execute(
            text(
                """
                INSERT INTO analytics.fct_metric_values
                (tenant_id, metric_id, definition_version, grain, bucket_start,
                 is_total, dim_repo, dim_team, value)
                VALUES
                (:tenant_id, :metric_id, 'test', :grain, :bucket_start,
                 :is_total, :dim_repo, '', :value)
                """
            ),
            {
                "tenant_id": tenant_id,
                "metric_id": metric_id,
                "grain": grain,
                "bucket_start": bucket_start,
                "is_total": is_total,
                "dim_repo": dim_repo,
                "value": value,
            },
        )
        await session.commit()


@pytest.mark.asyncio
async def test_metric_values_workspace_total(
    client: AsyncClient, fct_metric_values_table
):
    token, tenant = await _setup_tenant(client, email="values@example.com")
    tenant_id = uuid.UUID(tenant["id"])

    await _seed_metric_value(
        tenant_id,
        metric_id="propel.cycle_time",
        grain="day",
        bucket_start=datetime(2026, 6, 1, tzinfo=UTC),
        value=7200.0,
        is_total=True,
    )
    # Dimension breakdown rows must not appear in workspace totals.
    await _seed_metric_value(
        tenant_id,
        metric_id="propel.cycle_time",
        grain="day",
        bucket_start=datetime(2026, 6, 1, tzinfo=UTC),
        value=9999.0,
        is_total=False,
        dim_repo="acme/api",
    )
    await _seed_metric_value(
        uuid.uuid4(),
        metric_id="propel.cycle_time",
        grain="day",
        bucket_start=datetime(2026, 6, 1, tzinfo=UTC),
        value=1.0,
        is_total=True,
    )

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/values",
        params={
            "metric_id": "propel.cycle_time",
            "granularity": "daily",
            "start": "2026-06-01",
            "end": "2026-06-30",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric_id"] == "propel.cycle_time"
    assert body["granularity"] == "daily"
    assert body["unit"] == "duration"
    assert body["points"] == [{"period_start": "2026-06-01", "value": 7200.0}]


@pytest.mark.asyncio
async def test_metric_values_unknown_metric_404(
    client: AsyncClient, fct_metric_values_table
):
    token, tenant = await _setup_tenant(client, email="unknown-metric@example.com")
    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/values",
        params={"metric_id": "org.does_not_exist"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 404, resp.text


@pytest.fixture
async def fct_metric_values_table_legacy(db_engine):
    """Pre-is_total warehouse shape (empty dims = workspace total)."""
    async with db_engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS analytics"))
        await conn.execute(text("DROP TABLE IF EXISTS analytics.fct_metric_values"))
        await conn.execute(
            text(
                """
                CREATE TABLE analytics.fct_metric_values (
                    tenant_id uuid NOT NULL,
                    metric_id text NOT NULL,
                    definition_version text NOT NULL,
                    grain text NOT NULL,
                    bucket_start timestamptz NOT NULL,
                    bucket_end timestamptz,
                    is_complete boolean,
                    dim_repo text NOT NULL DEFAULT '',
                    dim_team text NOT NULL DEFAULT '',
                    value float8,
                    numerator float8,
                    denominator float8
                )
                """
            )
        )
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS analytics.fct_metric_values"))


@pytest.mark.asyncio
async def test_metric_values_legacy_schema_without_is_total(
    client: AsyncClient, fct_metric_values_table_legacy
):
    token, tenant = await _setup_tenant(client, email="legacy-values@example.com")
    tenant_id = uuid.UUID(tenant["id"])

    async with async_session_maker() as session:
        await session.execute(
            text(
                """
                INSERT INTO analytics.fct_metric_values
                (tenant_id, metric_id, definition_version, grain, bucket_start,
                 dim_repo, dim_team, value)
                VALUES
                (:tenant_id, 'propel.cycle_time', 'test', 'week',
                 :bucket_start, '', '', 3600.0)
                """
            ),
            {
                "tenant_id": tenant_id,
                "bucket_start": datetime(2026, 6, 2, tzinfo=UTC),
            },
        )
        await session.commit()

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/values",
        params={
            "metric_id": "propel.cycle_time",
            "granularity": "weekly",
            "start": "2026-06-01",
            "end": "2026-06-30",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["points"] == [{"period_start": "2026-06-02", "value": 3600.0}]


@pytest.mark.asyncio
async def test_metric_values_missing_table_empty(client: AsyncClient):
    token, tenant = await _setup_tenant(client, email="no-fct@example.com")
    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/metrics/values",
        params={
            "metric_id": "propel.cycle_time",
            "granularity": "weekly",
            "start": "2026-06-01",
            "end": "2026-06-30",
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric_id"] == "propel.cycle_time"
    assert body["points"] == []
