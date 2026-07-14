"""Read queries backing the analytics metrics endpoints.

Reads the dbt-built marts in the `analytics` Postgres schema (see
transformation/dbt). The marts are daily-grain; week/month granularity is a
`date_trunc` group-by at query time, so any granularity works without extra
models. All queries are tenant-scoped and read-only.

The `analytics` schema is owned by dbt, not Alembic — it may not exist yet on a
fresh database (dbt never ran). That case degrades to an empty series rather
than a 500 so the dashboard renders before the first analytics run.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.metrics import (
    ChangeFailurePoint,
    ChangeFailureResponse,
    CycleTimePoint,
    CycleTimeResponse,
    DeploymentFrequencyPoint,
    DeploymentFrequencyResponse,
    Granularity,
    ProjectActivityPoint,
    ProjectActivityResponse,
    PullRequestActivityPoint,
    PullRequestActivityResponse,
    ReviewCommentsPoint,
    ReviewCommentsResponse,
    ReviewLatencyPoint,
    ReviewLatencyResponse,
    TicketActivityPoint,
    TicketActivityResponse,
    TicketCommentsPoint,
    TicketCommentsResponse,
    TicketDescriptionEditsPoint,
    TicketDescriptionEditsResponse,
    WorkflowRunsPoint,
    WorkflowRunsResponse,
)

logger = logging.getLogger("propel.metrics")

_GRANULARITY_TO_TRUNC: dict[str, str] = {
    "daily": "day",
    "weekly": "week",
    "monthly": "month",
}

_PR_ACTIVITY_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(prs_opened), 0)::int AS opened,
        COALESCE(SUM(prs_merged), 0)::int AS merged,
        COALESCE(SUM(prs_closed), 0)::int AS closed
    FROM analytics.fct_pr_activity_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_DEPLOYMENT_FREQUENCY_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(releases_published), 0)::int AS releases_published,
        COALESCE(SUM(production_releases), 0)::int AS production_releases
    FROM analytics.fct_deployment_frequency_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

# Weighted median/p90 across days in a week/month bucket isn't available without
# the underlying PR rows, so we average the daily medians/p90s weighted by
# prs_merged. Avg cycle time is a true weighted mean of the daily averages.
_CYCLE_TIME_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(prs_merged), 0)::int AS prs_merged,
        (
            SUM(median_cycle_time_hours * prs_merged)
            / NULLIF(SUM(prs_merged), 0)
        )::float8 AS median_hours,
        (
            SUM(avg_cycle_time_hours * prs_merged)
            / NULLIF(SUM(prs_merged), 0)
        )::float8 AS avg_hours,
        (
            SUM(p90_cycle_time_hours * prs_merged)
            / NULLIF(SUM(prs_merged), 0)
        )::float8 AS p90_hours
    FROM analytics.fct_pr_cycle_time_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_REVIEW_LATENCY_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(prs_first_reviewed), 0)::int AS prs_first_reviewed,
        (
            SUM(median_time_to_first_review_hours * prs_first_reviewed)
            / NULLIF(SUM(CASE
                WHEN median_time_to_first_review_hours IS NULL THEN 0
                ELSE prs_first_reviewed
            END), 0)
        )::float8 AS median_hours_to_first_review,
        COALESCE(SUM(reviews_submitted), 0)::int AS reviews_submitted
    FROM analytics.fct_review_latency_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_CHANGE_FAILURE_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(prs_merged), 0)::int AS prs_merged,
        COALESCE(SUM(prs_reverted), 0)::int AS prs_reverted,
        (
            SUM(prs_reverted)::float8 / NULLIF(SUM(prs_merged), 0)
        )::float8 AS change_failure_rate
    FROM analytics.fct_change_failure_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_REVIEW_COMMENTS_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(review_comments_created), 0)::int AS review_comments_created
    FROM analytics.fct_review_comments_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_WORKFLOW_RUNS_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(runs_started), 0)::int AS runs_started,
        COALESCE(SUM(runs_completed), 0)::int AS runs_completed,
        COALESCE(SUM(runs_success), 0)::int AS runs_success,
        COALESCE(SUM(runs_failure), 0)::int AS runs_failure
    FROM analytics.fct_workflow_runs_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_TICKET_ACTIVITY_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(tickets_created), 0)::int AS tickets_created,
        COALESCE(SUM(tickets_completed), 0)::int AS tickets_completed,
        COALESCE(SUM(tickets_canceled), 0)::int AS tickets_canceled
    FROM analytics.fct_ticket_activity_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_TICKET_COMMENTS_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(comments_created), 0)::int AS comments_created
    FROM analytics.fct_ticket_comments_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_PROJECT_ACTIVITY_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(projects_created), 0)::int AS projects_created,
        COALESCE(SUM(projects_completed), 0)::int AS projects_completed,
        COALESCE(SUM(projects_canceled), 0)::int AS projects_canceled
    FROM analytics.fct_project_activity_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

_TICKET_DESCRIPTION_EDITS_QUERY = text(
    """
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(description_edits), 0)::int AS description_edits
    FROM analytics.fct_ticket_description_edits_daily
    WHERE tenant_id = :tenant_id
      AND activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)


def _bind(
    granularity: Granularity, tenant_id: uuid.UUID, start: date, end: date
) -> dict:
    return {
        "trunc_unit": _GRANULARITY_TO_TRUNC[granularity],
        "tenant_id": tenant_id,
        "start": start,
        "end": end,
    }


async def _safe_query(session: AsyncSession, query, params: dict, mart: str):
    try:
        result = await session.execute(query, params)
        return result.all()
    except ProgrammingError:
        await session.rollback()
        logger.warning("%s missing; returning empty series", mart)
        return []


async def pull_request_activity(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> PullRequestActivityResponse:
    rows = await _safe_query(
        session,
        _PR_ACTIVITY_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_pr_activity_daily",
    )
    return PullRequestActivityResponse(
        granularity=granularity,
        points=[
            PullRequestActivityPoint(
                period_start=period_start, opened=opened, merged=merged, closed=closed
            )
            for period_start, opened, merged, closed in rows
        ],
    )


async def deployment_frequency(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> DeploymentFrequencyResponse:
    rows = await _safe_query(
        session,
        _DEPLOYMENT_FREQUENCY_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_deployment_frequency_daily",
    )
    return DeploymentFrequencyResponse(
        granularity=granularity,
        points=[
            DeploymentFrequencyPoint(
                period_start=period_start,
                releases_published=releases_published,
                production_releases=production_releases,
            )
            for period_start, releases_published, production_releases in rows
        ],
    )


async def cycle_time(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> CycleTimeResponse:
    rows = await _safe_query(
        session,
        _CYCLE_TIME_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_pr_cycle_time_daily",
    )
    return CycleTimeResponse(
        granularity=granularity,
        points=[
            CycleTimePoint(
                period_start=period_start,
                prs_merged=prs_merged,
                median_hours=median_hours,
                avg_hours=avg_hours,
                p90_hours=p90_hours,
            )
            for period_start, prs_merged, median_hours, avg_hours, p90_hours in rows
        ],
    )


async def review_latency(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> ReviewLatencyResponse:
    rows = await _safe_query(
        session,
        _REVIEW_LATENCY_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_review_latency_daily",
    )
    return ReviewLatencyResponse(
        granularity=granularity,
        points=[
            ReviewLatencyPoint(
                period_start=period_start,
                prs_first_reviewed=prs_first_reviewed,
                median_hours_to_first_review=median_hours,
                reviews_submitted=reviews_submitted,
            )
            for (
                period_start,
                prs_first_reviewed,
                median_hours,
                reviews_submitted,
            ) in rows
        ],
    )


async def change_failure(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> ChangeFailureResponse:
    rows = await _safe_query(
        session,
        _CHANGE_FAILURE_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_change_failure_daily",
    )
    return ChangeFailureResponse(
        granularity=granularity,
        points=[
            ChangeFailurePoint(
                period_start=period_start,
                prs_merged=prs_merged,
                prs_reverted=prs_reverted,
                change_failure_rate=rate,
            )
            for period_start, prs_merged, prs_reverted, rate in rows
        ],
    )


async def review_comments(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> ReviewCommentsResponse:
    rows = await _safe_query(
        session,
        _REVIEW_COMMENTS_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_review_comments_daily",
    )
    return ReviewCommentsResponse(
        granularity=granularity,
        points=[
            ReviewCommentsPoint(
                period_start=period_start,
                review_comments_created=count,
            )
            for period_start, count in rows
        ],
    )


async def workflow_runs(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> WorkflowRunsResponse:
    rows = await _safe_query(
        session,
        _WORKFLOW_RUNS_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_workflow_runs_daily",
    )
    return WorkflowRunsResponse(
        granularity=granularity,
        points=[
            WorkflowRunsPoint(
                period_start=period_start,
                runs_started=started,
                runs_completed=completed,
                runs_success=success,
                runs_failure=failure,
            )
            for period_start, started, completed, success, failure in rows
        ],
    )


async def ticket_activity(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> TicketActivityResponse:
    rows = await _safe_query(
        session,
        _TICKET_ACTIVITY_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_ticket_activity_daily",
    )
    return TicketActivityResponse(
        granularity=granularity,
        points=[
            TicketActivityPoint(
                period_start=period_start,
                tickets_created=created,
                tickets_completed=completed,
                tickets_canceled=canceled,
            )
            for period_start, created, completed, canceled in rows
        ],
    )


async def ticket_comments(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> TicketCommentsResponse:
    rows = await _safe_query(
        session,
        _TICKET_COMMENTS_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_ticket_comments_daily",
    )
    return TicketCommentsResponse(
        granularity=granularity,
        points=[
            TicketCommentsPoint(
                period_start=period_start,
                comments_created=count,
            )
            for period_start, count in rows
        ],
    )


async def project_activity(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> ProjectActivityResponse:
    rows = await _safe_query(
        session,
        _PROJECT_ACTIVITY_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_project_activity_daily",
    )
    return ProjectActivityResponse(
        granularity=granularity,
        points=[
            ProjectActivityPoint(
                period_start=period_start,
                projects_created=created,
                projects_completed=completed,
                projects_canceled=canceled,
            )
            for period_start, created, completed, canceled in rows
        ],
    )


async def ticket_description_edits(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> TicketDescriptionEditsResponse:
    rows = await _safe_query(
        session,
        _TICKET_DESCRIPTION_EDITS_QUERY,
        _bind(granularity, tenant_id, start, end),
        "analytics.fct_ticket_description_edits_daily",
    )
    return TicketDescriptionEditsResponse(
        granularity=granularity,
        points=[
            TicketDescriptionEditsPoint(
                period_start=period_start,
                description_edits=count,
            )
            for period_start, count in rows
        ],
    )
