"""Read queries backing the analytics metrics endpoints.

Reads the dbt-built marts in the `analytics` Postgres schema (see
transformation/dbt). The marts are daily-grain; week/month granularity is a
`date_trunc` group-by at query time, so any granularity works without extra
models. All queries are tenant-scoped and read-only.

The `analytics` schema is owned by dbt, not Alembic — it may not exist yet on a
fresh database (dbt never ran). That case degrades to an empty series rather
than a 500 so the dashboard renders before the first analytics run.

Person-scoped (`scope=me`) variants can't use the marts — those are
(tenant, day) grain with no person column, and percentiles can't be re-filtered
after aggregation. They query `raw_record` (the same L0 the dbt staging views
read) row-level, filtered by the caller's GitHub login, mirroring the
snapshot/attribution semantics of `stg_github_pull_requests` /
`stg_github_reviews`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import IntegrationProvider
from app.models.external_identity import ExternalIdentity
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

# --------------------------------------------------------------------------- #
# Person-scoped (`scope=me`) queries
#
# raw_record is append-only: each re-sync of a PR/review lands a new row, so
# DISTINCT ON (node_id) ... ORDER BY fetched_at DESC picks the current
# snapshot — the same convention as the dbt staging views. The author filter
# is safe inside the snapshot CTE because a PR's author never changes.
# --------------------------------------------------------------------------- #

_PR_SNAPSHOT_CTE = """
    prs AS (
        SELECT DISTINCT ON (payload ->> 'node_id')
            payload ->> 'node_id' AS pr_node_id,
            (payload ->> 'number')::int AS pr_number,
            (payload ->> 'created_at')::timestamptz AS created_at,
            (payload ->> 'closed_at')::timestamptz AS closed_at,
            (payload ->> 'merged_at')::timestamptz AS merged_at,
            payload -> 'user' ->> 'login' AS author_login,
            COALESCE(
                payload -> 'base' -> 'repo' ->> 'full_name',
                NULLIF(CONCAT(payload ->> 'org', '/', payload ->> 'repo'), '/')
            ) AS repo,
            COALESCE(payload ->> 'title', '')
                ~* '^revert([[:space:][:punct:]]|$)' AS is_revert,
            CASE
                WHEN
                    (payload ->> 'merged_at') IS NOT NULL
                    AND (payload ->> 'created_at') IS NOT NULL
                    THEN EXTRACT(
                        EPOCH FROM (
                            (payload ->> 'merged_at')::timestamptz
                            - (payload ->> 'created_at')::timestamptz
                        )
                    ) / 3600.0
            END AS cycle_time_hours
        FROM raw_record
        WHERE tenant_id = :tenant_id
          AND source = 'github'
          AND resource_type = 'pull_requests'
          AND payload ->> 'node_id' IS NOT NULL
          AND payload -> 'user' ->> 'login' = :author_login
        ORDER BY payload ->> 'node_id' ASC, fetched_at DESC
    )
"""

_PR_ACTIVITY_ME_QUERY = text(
    f"""
    WITH {_PR_SNAPSHOT_CTE},
    activity AS (
        SELECT
            (created_at AT TIME ZONE 'UTC')::date AS activity_date,
            1 AS opened, 0 AS merged, 0 AS closed
        FROM prs
        WHERE created_at IS NOT NULL

        UNION ALL

        SELECT
            (merged_at AT TIME ZONE 'UTC')::date AS activity_date,
            0 AS opened, 1 AS merged, 0 AS closed
        FROM prs
        WHERE merged_at IS NOT NULL

        UNION ALL

        SELECT
            (closed_at AT TIME ZONE 'UTC')::date AS activity_date,
            0 AS opened, 0 AS merged, 1 AS closed
        FROM prs
        WHERE closed_at IS NOT NULL AND merged_at IS NULL
    )
    SELECT
        date_trunc(:trunc_unit, activity_date)::date AS period_start,
        COALESCE(SUM(opened), 0)::int AS opened,
        COALESCE(SUM(merged), 0)::int AS merged,
        COALESCE(SUM(closed), 0)::int AS closed
    FROM activity
    WHERE activity_date >= :start
      AND activity_date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

# Unlike the mart path (weighted average of daily medians), row-level access
# lets us compute true percentiles per period.
_CYCLE_TIME_ME_QUERY = text(
    f"""
    WITH {_PR_SNAPSHOT_CTE}
    SELECT
        date_trunc(
            :trunc_unit, (merged_at AT TIME ZONE 'UTC')::date
        )::date AS period_start,
        COUNT(*)::int AS prs_merged,
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY cycle_time_hours
        )::float8 AS median_hours,
        AVG(cycle_time_hours)::float8 AS avg_hours,
        percentile_cont(0.9) WITHIN GROUP (
            ORDER BY cycle_time_hours
        )::float8 AS p90_hours
    FROM prs
    WHERE merged_at IS NOT NULL
      AND cycle_time_hours IS NOT NULL
      AND cycle_time_hours >= 0
      AND (merged_at AT TIME ZONE 'UTC')::date >= :start
      AND (merged_at AT TIME ZONE 'UTC')::date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)

# scope=me semantics: latency for MY authored PRs to receive their first
# non-self review; reviews_submitted counts reviews others left on my PRs.
_REVIEW_LATENCY_ME_QUERY = text(
    f"""
    WITH {_PR_SNAPSHOT_CTE},
    reviews AS (
        SELECT DISTINCT ON (payload ->> 'node_id')
            (payload ->> 'submitted_at')::timestamptz AS submitted_at,
            payload -> 'user' ->> 'login' AS reviewer_login,
            (payload ->> 'pull_request_number')::int AS pull_request_number,
            NULLIF(CONCAT(payload ->> 'org', '/', payload ->> 'repo'), '/') AS repo
        FROM raw_record
        WHERE tenant_id = :tenant_id
          AND source = 'github'
          AND resource_type = 'reviews'
          AND payload ->> 'node_id' IS NOT NULL
          AND payload ->> 'submitted_at' IS NOT NULL
          AND COALESCE(payload ->> 'state', '') <> 'PENDING'
        ORDER BY payload ->> 'node_id' ASC, fetched_at DESC
    ),
    pr_reviews AS (
        SELECT
            prs.pr_node_id,
            prs.created_at,
            reviews.submitted_at
        FROM prs
        INNER JOIN reviews
            ON reviews.repo IS NOT DISTINCT FROM prs.repo
            AND reviews.pull_request_number = prs.pr_number
            AND reviews.reviewer_login IS DISTINCT FROM prs.author_login
        WHERE prs.created_at IS NOT NULL
    ),
    first_review AS (
        SELECT
            pr_node_id,
            MIN(submitted_at) AS first_reviewed_at,
            EXTRACT(
                EPOCH FROM (MIN(submitted_at) - created_at)
            ) / 3600.0 AS hours_to_first_review
        FROM pr_reviews
        GROUP BY pr_node_id, created_at
    ),
    first_reviewed_period AS (
        SELECT
            date_trunc(
                :trunc_unit, (first_reviewed_at AT TIME ZONE 'UTC')::date
            )::date AS period_start,
            COUNT(*)::int AS prs_first_reviewed,
            percentile_cont(0.5) WITHIN GROUP (
                ORDER BY hours_to_first_review
            )::float8 AS median_hours_to_first_review
        FROM first_review
        WHERE hours_to_first_review IS NOT NULL
          AND hours_to_first_review >= 0
          AND (first_reviewed_at AT TIME ZONE 'UTC')::date >= :start
          AND (first_reviewed_at AT TIME ZONE 'UTC')::date <= :end
        GROUP BY 1
    ),
    reviews_period AS (
        SELECT
            date_trunc(
                :trunc_unit, (submitted_at AT TIME ZONE 'UTC')::date
            )::date AS period_start,
            COUNT(*)::int AS reviews_submitted
        FROM pr_reviews
        WHERE (submitted_at AT TIME ZONE 'UTC')::date >= :start
          AND (submitted_at AT TIME ZONE 'UTC')::date <= :end
        GROUP BY 1
    )
    SELECT
        period_start,
        COALESCE(f.prs_first_reviewed, 0)::int AS prs_first_reviewed,
        f.median_hours_to_first_review,
        COALESCE(r.reviews_submitted, 0)::int AS reviews_submitted
    FROM first_reviewed_period AS f
    FULL OUTER JOIN reviews_period AS r USING (period_start)
    ORDER BY 1
    """
)

# Caveat inherited from the mart: attribution is the author of the
# revert-titled PR, not the author of the original failing change.
_CHANGE_FAILURE_ME_QUERY = text(
    f"""
    WITH {_PR_SNAPSHOT_CTE}
    SELECT
        date_trunc(
            :trunc_unit, (merged_at AT TIME ZONE 'UTC')::date
        )::date AS period_start,
        COUNT(*)::int AS prs_merged,
        COUNT(*) FILTER (WHERE is_revert)::int AS prs_reverted,
        CASE
            WHEN COUNT(*) = 0 THEN NULL
            ELSE (COUNT(*) FILTER (WHERE is_revert))::float8 / COUNT(*)::float8
        END AS change_failure_rate
    FROM prs
    WHERE merged_at IS NOT NULL
      AND (merged_at AT TIME ZONE 'UTC')::date >= :start
      AND (merged_at AT TIME ZONE 'UTC')::date <= :end
    GROUP BY 1
    ORDER BY 1
    """
)


async def resolve_github_login(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """The caller's GitHub @login in this tenant, or None when unlinked."""
    return await session.scalar(
        select(ExternalIdentity.external_login)
        .where(
            ExternalIdentity.tenant_id == tenant_id,
            ExternalIdentity.propel_user_id == user_id,
            ExternalIdentity.provider == IntegrationProvider.github,
            ExternalIdentity.external_login.is_not(None),
        )
        .limit(1)
    )


def _bind(
    granularity: Granularity,
    tenant_id: uuid.UUID,
    start: date,
    end: date,
    author_login: str | None = None,
) -> dict:
    params = {
        "trunc_unit": _GRANULARITY_TO_TRUNC[granularity],
        "tenant_id": tenant_id,
        "start": start,
        "end": end,
    }
    if author_login is not None:
        params["author_login"] = author_login
    return params


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
    author_login: str | None = None,
) -> PullRequestActivityResponse:
    if author_login is not None:
        query, mart = _PR_ACTIVITY_ME_QUERY, "raw_record"
    else:
        query, mart = _PR_ACTIVITY_QUERY, "analytics.fct_pr_activity_daily"
    rows = await _safe_query(
        session,
        query,
        _bind(granularity, tenant_id, start, end, author_login),
        mart,
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
    author_login: str | None = None,
) -> CycleTimeResponse:
    if author_login is not None:
        query, mart = _CYCLE_TIME_ME_QUERY, "raw_record"
    else:
        query, mart = _CYCLE_TIME_QUERY, "analytics.fct_pr_cycle_time_daily"
    rows = await _safe_query(
        session,
        query,
        _bind(granularity, tenant_id, start, end, author_login),
        mart,
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
    author_login: str | None = None,
) -> ReviewLatencyResponse:
    if author_login is not None:
        query, mart = _REVIEW_LATENCY_ME_QUERY, "raw_record"
    else:
        query, mart = _REVIEW_LATENCY_QUERY, "analytics.fct_review_latency_daily"
    rows = await _safe_query(
        session,
        query,
        _bind(granularity, tenant_id, start, end, author_login),
        mart,
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
    author_login: str | None = None,
) -> ChangeFailureResponse:
    if author_login is not None:
        query, mart = _CHANGE_FAILURE_ME_QUERY, "raw_record"
    else:
        query, mart = _CHANGE_FAILURE_QUERY, "analytics.fct_change_failure_daily"
    rows = await _safe_query(
        session,
        query,
        _bind(granularity, tenant_id, start, end, author_login),
        mart,
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
