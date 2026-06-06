import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    check_can_invite,
    require_any_permission,
    require_permission,
)
from app.auth.manager import current_active_user
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.invite import InviteAcceptRead, InviteCreate, InviteCreated, InviteRead
from app.services import invites as invite_service

router = APIRouter(prefix="/api/v1", tags=["invites"])


@router.post(
    "/tenants/{tenant_id}/invites",
    response_model=InviteCreated,
    status_code=201,
)
async def create_invite(
    payload: InviteCreate,
    ctx=Depends(
        require_any_permission(
            "invites:role:admin",
            "invites:role:manager",
            "invites:role:individual",
        )
    ),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    check_can_invite(ctx, payload.role)
    return await invite_service.create_invite(session, ctx.tenant.id, user, payload)


@router.get(
    "/tenants/{tenant_id}/invites",
    response_model=list[InviteRead],
)
async def list_invites(
    ctx=Depends(require_permission("invites:read")),
    session: AsyncSession = Depends(get_async_session),
):
    return await invite_service.list_pending_invites(session, ctx.tenant.id)


@router.delete(
    "/tenants/{tenant_id}/invites/{invite_id}",
    status_code=204,
)
async def revoke_invite(
    invite_id: uuid.UUID,
    ctx=Depends(require_permission("invites:revoke")),
    session: AsyncSession = Depends(get_async_session),
):
    await invite_service.revoke_invite(session, ctx.tenant.id, invite_id)


@router.post(
    "/invites/{token}/accept",
    response_model=InviteAcceptRead,
)
async def accept_invite(
    token: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    membership = await invite_service.accept_invite(session, user, token)
    return InviteAcceptRead(tenant_id=membership.tenant_id, role=membership.role)
