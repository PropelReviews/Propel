import uuid
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import INVITE_ROLE_PERMISSIONS
from app.auth.session import get_current_user
from app.db.session import get_async_session
from app.models.enums import MembershipStatus, Role
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User
from app.services.role_permissions import get_effective_permissions


@dataclass
class TenantContext:
    tenant: Tenant
    membership: TenantMembership
    permissions: set[str] = field(default_factory=set)


async def get_membership(
    tenant_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> TenantMembership:
    result = await session.execute(
        select(TenantMembership)
        .join(Tenant)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user.id,
            TenantMembership.status == MembershipStatus.active,
            Tenant.deleted_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    return membership


async def get_tenant_context(
    membership: TenantMembership = Depends(get_membership),
    session: AsyncSession = Depends(get_async_session),
) -> TenantContext:
    tenant = await session.get(Tenant, membership.tenant_id)
    if tenant is None or tenant.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found"
        )
    permissions = await get_effective_permissions(session, tenant.id, membership.role)
    return TenantContext(tenant=tenant, membership=membership, permissions=permissions)


def require_permission(*keys: str, detail: str = "Forbidden"):
    """Dependency factory: caller's role must hold every listed permission."""

    def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not set(keys) <= ctx.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return ctx

    return dependency


def require_any_permission(*keys: str, detail: str = "Forbidden"):
    """Dependency factory: caller's role must hold at least one permission."""

    def dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not set(keys) & ctx.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return ctx

    return dependency


require_member = require_permission("tenant:read")


def check_can_invite(ctx: TenantContext, invitee_role: Role) -> None:
    if INVITE_ROLE_PERMISSIONS[invitee_role] not in ctx.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot invite role '{invitee_role.value}'",
        )
