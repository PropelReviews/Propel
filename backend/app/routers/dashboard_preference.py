"""Per-user dashboard layout backup endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_permission
from app.auth.manager import current_active_user
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.dashboard_preference import (
    DashboardPreferencePut,
    DashboardPreferenceRead,
)
from app.services import dashboard_preference as svc

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get(
    "/tenants/{tenant_id}/dashboard-preference",
    response_model=DashboardPreferenceRead,
)
async def get_dashboard_preference(
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    row = await svc.get_preference(session, tenant_id=ctx.tenant.id, user_id=user.id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No dashboard preference saved",
        )
    return DashboardPreferenceRead.model_validate(row)


@router.put(
    "/tenants/{tenant_id}/dashboard-preference",
    response_model=DashboardPreferenceRead,
)
async def put_dashboard_preference(
    body: DashboardPreferencePut,
    ctx=Depends(require_permission("metrics:read")),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    row = await svc.upsert_preference(
        session,
        tenant_id=ctx.tenant.id,
        user_id=user.id,
        layout=body.layout,
    )
    return DashboardPreferenceRead.model_validate(row)
