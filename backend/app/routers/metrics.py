"""Read-only analytics metrics endpoints (dbt marts, the SPA dashboard charts).

Tenant-scoped, gated by the `metrics:read` permission (granted to every
role by default), since these are views, not control surfaces.
"""

from datetime import UTC, datetime, timedelta
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_async_session
from app.schemas.metrics import Granularity, PullRequestActivityResponse
from app.services import metrics as metrics_service

router = APIRouter(prefix="/api/v1", tags=["metrics"])

_DEFAULT_WINDOW_DAYS = 90


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
    resolved_end = end or datetime.now(UTC).date()
    resolved_start = start or resolved_end - timedelta(days=_DEFAULT_WINDOW_DAYS)
    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    return await metrics_service.pull_request_activity(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )
