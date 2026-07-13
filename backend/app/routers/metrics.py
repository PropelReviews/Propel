"""Read-only analytics metrics endpoints (dbt marts, the SPA dashboard charts).

Tenant-scoped, gated by the `metrics:read` permission (granted to every
role by default), since these are views, not control surfaces.

Endpoints map onto DORA-aligned primitives computed in transformation/dbt:
  GET .../metrics/pull-requests     deployment-frequency proxy
  GET .../metrics/cycle-time        lead-time-for-changes proxy
  GET .../metrics/review-latency    review-flow / lead-time breakdown
  GET .../metrics/change-failure    change-fail-rate proxy (reverts)
"""

from datetime import UTC, datetime, timedelta
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_async_session
from app.schemas.metrics import (
    ChangeFailureResponse,
    CycleTimeResponse,
    Granularity,
    PullRequestActivityResponse,
    ReviewLatencyResponse,
)
from app.services import metrics as metrics_service

router = APIRouter(prefix="/api/v1", tags=["metrics"])

_DEFAULT_WINDOW_DAYS = 90


def _resolve_range(
    start: date_type | None, end: date_type | None
) -> tuple[date_type, date_type]:
    resolved_end = end or datetime.now(UTC).date()
    resolved_start = start or resolved_end - timedelta(days=_DEFAULT_WINDOW_DAYS)
    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    return resolved_start, resolved_end


@router.get(
    "/tenants/{tenant_id}/metrics/pull-requests",
    response_model=PullRequestActivityResponse,
)
async def get_pull_request_activity(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.pull_request_activity(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/cycle-time",
    response_model=CycleTimeResponse,
)
async def get_cycle_time(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.cycle_time(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/review-latency",
    response_model=ReviewLatencyResponse,
)
async def get_review_latency(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.review_latency(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/change-failure",
    response_model=ChangeFailureResponse,
)
async def get_change_failure(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.change_failure(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )
