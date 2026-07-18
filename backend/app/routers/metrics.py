"""Read-only analytics metrics endpoints (dbt marts, the SPA dashboard charts).

Tenant-scoped, gated by the `metrics:read` permission (granted to every
role by default), since these are views, not control surfaces.

Endpoints map onto DORA-aligned primitives computed in transformation/dbt:
  GET .../metrics/deployment-frequency  published GitHub Releases
  GET .../metrics/pull-requests         PR throughput (opened/merged/closed)
  GET .../metrics/cycle-time            lead-time-for-changes proxy
  GET .../metrics/review-latency        review-flow / lead-time breakdown
  GET .../metrics/change-failure        change-fail-rate proxy (reverts)

The four PR-based endpoints accept `?scope=me`, which restricts the series to
the caller's own authored work. The GitHub login is resolved server-side from
the caller's linked identity; an unlinked user gets an empty series.
Deployment frequency stays org-scoped — releases aren't IC-attributable.
  GET .../metrics/review-comments       PR review-comment throughput
  GET .../metrics/workflow-runs         GitHub Actions run activity
  GET .../metrics/tickets               ticket activity (all trackers)
  GET .../metrics/ticket-comments       ticket comment throughput
  GET .../metrics/projects              project activity
  GET .../metrics/ticket-description-edits  ticket description edits
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
    DeploymentFrequencyResponse,
    Granularity,
    MetricScope,
    ProjectActivityResponse,
    PullRequestActivityResponse,
    ReviewCommentsResponse,
    ReviewLatencyResponse,
    TicketActivityResponse,
    TicketCommentsResponse,
    TicketDescriptionEditsResponse,
    WorkflowRunsResponse,
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


async def _resolve_scope_login(
    session: AsyncSession, ctx, scope: MetricScope
) -> tuple[str | None, bool]:
    """(author_login, is_unlinked_me) for a metrics request.

    scope=org → (None, False). scope=me with a linked GitHub identity →
    (login, False). scope=me while unlinked → (None, True): callers should
    return an empty series rather than fall back to org-wide data.
    """
    if scope != "me":
        return None, False
    login = await metrics_service.resolve_github_login(
        session,
        tenant_id=ctx.tenant.id,
        user_id=ctx.membership.user_id,
    )
    return login, login is None


@router.get(
    "/tenants/{tenant_id}/metrics/pull-requests",
    response_model=PullRequestActivityResponse,
)
async def get_pull_request_activity(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    scope: MetricScope = Query(default="org"),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    author_login, unlinked = await _resolve_scope_login(session, ctx, scope)
    if unlinked:
        return PullRequestActivityResponse(granularity=granularity, points=[])
    return await metrics_service.pull_request_activity(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
        author_login=author_login,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/deployment-frequency",
    response_model=DeploymentFrequencyResponse,
)
async def get_deployment_frequency(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.deployment_frequency(
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
    scope: MetricScope = Query(default="org"),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    author_login, unlinked = await _resolve_scope_login(session, ctx, scope)
    if unlinked:
        return CycleTimeResponse(granularity=granularity, points=[])
    return await metrics_service.cycle_time(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
        author_login=author_login,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/review-latency",
    response_model=ReviewLatencyResponse,
)
async def get_review_latency(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    scope: MetricScope = Query(default="org"),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    author_login, unlinked = await _resolve_scope_login(session, ctx, scope)
    if unlinked:
        return ReviewLatencyResponse(granularity=granularity, points=[])
    return await metrics_service.review_latency(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
        author_login=author_login,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/change-failure",
    response_model=ChangeFailureResponse,
)
async def get_change_failure(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    scope: MetricScope = Query(default="org"),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    author_login, unlinked = await _resolve_scope_login(session, ctx, scope)
    if unlinked:
        return ChangeFailureResponse(granularity=granularity, points=[])
    return await metrics_service.change_failure(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
        author_login=author_login,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/review-comments",
    response_model=ReviewCommentsResponse,
)
async def get_review_comments(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.review_comments(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/workflow-runs",
    response_model=WorkflowRunsResponse,
)
async def get_workflow_runs(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.workflow_runs(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/tickets",
    response_model=TicketActivityResponse,
)
async def get_ticket_activity(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.ticket_activity(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/ticket-comments",
    response_model=TicketCommentsResponse,
)
async def get_ticket_comments(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.ticket_comments(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/projects",
    response_model=ProjectActivityResponse,
)
async def get_project_activity(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.project_activity(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )


@router.get(
    "/tenants/{tenant_id}/metrics/ticket-description-edits",
    response_model=TicketDescriptionEditsResponse,
)
async def get_ticket_description_edits(
    granularity: Granularity = Query(default="daily"),
    start: date_type | None = Query(default=None),
    end: date_type | None = Query(default=None),
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
):
    resolved_start, resolved_end = _resolve_range(start, end)
    return await metrics_service.ticket_description_edits(
        session,
        ctx.tenant.id,
        granularity=granularity,
        start=resolved_start,
        end=resolved_end,
    )
