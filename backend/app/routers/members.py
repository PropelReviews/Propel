import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_admin_for_remove,
    require_admin_for_roles,
    require_member,
)
from app.db.session import get_async_session
from app.schemas.membership import MemberRead, MemberRoleUpdate
from app.services import members as member_service

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}/members", tags=["members"])


@router.get("/", response_model=list[MemberRead])
async def list_members(
    ctx=Depends(require_member),
    session: AsyncSession = Depends(get_async_session),
):
    return await member_service.list_members(session, ctx.tenant.id)


@router.patch("/{user_id}/role", response_model=MemberRead)
async def assign_role(
    user_id: uuid.UUID,
    payload: MemberRoleUpdate,
    ctx=Depends(require_admin_for_roles),
    session: AsyncSession = Depends(get_async_session),
):
    return await member_service.assign_role(session, ctx.tenant.id, user_id, payload)


@router.delete("/{user_id}", status_code=204)
async def remove_member(
    user_id: uuid.UUID,
    ctx=Depends(require_admin_for_remove),
    session: AsyncSession = Depends(get_async_session),
):
    await member_service.remove_member(session, ctx.tenant.id, user_id)
