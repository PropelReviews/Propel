import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import check_can_invite, require_invite_manager
from app.auth.manager import current_active_user
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.invite import InviteAcceptRead, InviteCreate, InviteCreated, InviteRead
from app.services import invites as invite_service

router = APIRouter(tags=["invites"])


@router.post(
    "/api/v1/tenants/{tenant_id}/invites",
    response_model=InviteCreated,
    status_code=201,
)
async def create_invite(
    payload: InviteCreate,
    ctx=Depends(require_invite_manager),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    check_can_invite(ctx.membership.role, payload.role)
    return await invite_service.create_invite(session, ctx.tenant.id, user, payload)


@router.get(
    "/api/v1/tenants/{tenant_id}/invites",
    response_model=list[InviteRead],
)
async def list_invites(
    ctx=Depends(require_invite_manager),
    session: AsyncSession = Depends(get_async_session),
):
    return await invite_service.list_pending_invites(session, ctx.tenant.id)


@router.delete(
    "/api/v1/tenants/{tenant_id}/invites/{invite_id}",
    status_code=204,
)
async def revoke_invite(
    invite_id: uuid.UUID,
    ctx=Depends(require_invite_manager),
    session: AsyncSession = Depends(get_async_session),
):
    await invite_service.revoke_invite(session, ctx.tenant.id, invite_id)


@router.post(
    "/api/v1/invites/{token}/accept",
    response_model=InviteAcceptRead,
)
async def accept_invite(
    token: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    membership = await invite_service.accept_invite(session, user, token)
    return InviteAcceptRead(tenant_id=membership.tenant_id, role=membership.role)
