"""Read-only ingestion observability endpoints (the SPA "Data" page).

Tenant-scoped, gated by the `ingestion:read` permission (granted to every
role by default), since this is a view, not a control surface.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.db.session import get_async_session
from app.schemas.ingestion import IngestionRunRead, IngestionStats
from app.services import ingestion as ingestion_service

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


@router.get(
    "/tenants/{tenant_id}/ingestion/runs",
    response_model=list[IngestionRunRead],
)
async def list_ingestion_runs(
    limit: int = Query(default=20, ge=1, le=100),
    ctx=Depends(require_permission("ingestion:read")),
    session: AsyncSession = Depends(get_async_session),
):
    runs = await ingestion_service.list_recent_runs(session, ctx.tenant.id, limit=limit)
    return [IngestionRunRead.model_validate(r) for r in runs]


@router.get(
    "/tenants/{tenant_id}/ingestion/stats",
    response_model=IngestionStats,
)
async def get_ingestion_stats(
    ctx=Depends(require_permission("ingestion:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return await ingestion_service.datapoint_stats(session, ctx.tenant.id)
