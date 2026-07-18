"""CRUD for per-user dashboard layout backups."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_preference import DashboardPreference
from app.schemas.dashboard_preference import DashboardLayoutV2


async def get_preference(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> DashboardPreference | None:
    result = await session.execute(
        select(DashboardPreference).where(
            DashboardPreference.tenant_id == tenant_id,
            DashboardPreference.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def upsert_preference(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    layout: DashboardLayoutV2 | dict[str, Any],
) -> DashboardPreference:
    payload = (
        layout.model_dump()
        if isinstance(layout, DashboardLayoutV2)
        else DashboardLayoutV2.model_validate(layout).model_dump()
    )
    row = await get_preference(session, tenant_id=tenant_id, user_id=user_id)
    if row is None:
        row = DashboardPreference(
            tenant_id=tenant_id,
            user_id=user_id,
            layout=payload,
        )
        session.add(row)
    else:
        row.layout = payload
    try:
        await session.commit()
    except Exception as exc:  # pragma: no cover - defensive
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not save dashboard preference",
        ) from exc
    await session.refresh(row)
    return row
