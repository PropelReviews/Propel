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
    Granularity,
    PullRequestActivityPoint,
    PullRequestActivityResponse,
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


async def pull_request_activity(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    granularity: Granularity,
    start: date,
    end: date,
) -> PullRequestActivityResponse:
    try:
        result = await session.execute(
            _PR_ACTIVITY_QUERY,
            {
                "trunc_unit": _GRANULARITY_TO_TRUNC[granularity],
                "tenant_id": tenant_id,
                "start": start,
                "end": end,
            },
        )
        rows = result.all()
    except ProgrammingError:
        # analytics.fct_pr_activity_daily does not exist yet (dbt never ran).
        await session.rollback()
        logger.warning(
            "analytics.fct_pr_activity_daily missing; returning empty PR activity"
        )
        rows = []

    return PullRequestActivityResponse(
        granularity=granularity,
        points=[
            PullRequestActivityPoint(
                period_start=period_start, opened=opened, merged=merged, closed=closed
            )
            for period_start, opened, merged, closed in rows
        ],
    )
