import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.manager import current_active_user
from app.auth.permissions import (
    can_assign_roles,
    can_delete_tenant,
    can_invite_role,
    can_list_members,
    can_manage_invites,
    can_remove_members,
    can_update_tenant,
)
from app.db.session import get_async_session
from app.models.enums import Role
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User


@dataclass
class TenantContext:
    tenant: Tenant
    membership: TenantMembership


async def get_membership(
    tenant_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> TenantMembership:
    result = await session.execute(
        select(TenantMembership)
        .join(Tenant)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user.id,
            Tenant.deleted_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return membership


async def get_tenant_context(
    membership: TenantMembership = Depends(get_membership),
    session: AsyncSession = Depends(get_async_session),
) -> TenantContext:
    tenant = await session.get(Tenant, membership.tenant_id)
    if tenant is None or tenant.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantContext(tenant=tenant, membership=membership)


def require_member(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not can_list_members(ctx.membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ctx


def require_admin(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not can_update_tenant(ctx.membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return ctx


def require_admin_for_delete(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not can_delete_tenant(ctx.membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return ctx


def require_admin_for_roles(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not can_assign_roles(ctx.membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return ctx


def require_admin_for_remove(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not can_remove_members(ctx.membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return ctx


def require_invite_manager(
    ctx: TenantContext = Depends(get_tenant_context),
) -> TenantContext:
    if not can_manage_invites(ctx.membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ctx


def check_can_invite(inviter_role: Role, invitee_role: Role) -> None:
    if not can_invite_role(inviter_role, invitee_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot invite role '{invitee_role.value}'",
        )
