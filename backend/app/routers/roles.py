"""Role permission management (the admin "Access" page).

The permission catalog is static; per-tenant grants live in
tenant_role_permissions and are edited here by holders of `roles:manage`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_tenant_context, require_permission
from app.auth.manager import current_active_user
from app.db.session import get_async_session
from app.models.enums import Role
from app.schemas.roles import (
    PermissionDefinitionRead,
    RolePermissionsRead,
    RolePermissionsUpdate,
    TenantMembershipRead,
)
from app.services import role_permissions as role_permission_service

router = APIRouter(prefix="/api/v1", tags=["roles"])


@router.get("/permissions/catalog", response_model=list[PermissionDefinitionRead])
async def permission_catalog(_=Depends(current_active_user)):
    return role_permission_service.catalog()


@router.get("/tenants/{tenant_id}/roles", response_model=list[RolePermissionsRead])
async def list_role_permissions(
    ctx=Depends(require_permission("roles:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    grants = await role_permission_service.get_all_role_permissions(
        session, ctx.tenant.id
    )
    return [
        RolePermissionsRead(role=role, permissions=sorted(grants.get(role, set())))
        for role in Role
    ]


@router.put("/tenants/{tenant_id}/roles/{role}", response_model=RolePermissionsRead)
async def update_role_permissions(
    role: Role,
    payload: RolePermissionsUpdate,
    ctx=Depends(require_permission("roles:manage")),
    session: AsyncSession = Depends(get_async_session),
):
    granted = await role_permission_service.set_role_permissions(
        session, ctx.tenant.id, role, payload.permissions
    )
    return RolePermissionsRead(role=role, permissions=sorted(granted))


@router.get("/tenants/{tenant_id}/membership/me", response_model=TenantMembershipRead)
async def my_membership(ctx=Depends(get_tenant_context)):
    return TenantMembershipRead(
        tenant_id=ctx.tenant.id,
        role=ctx.membership.role,
        permissions=sorted(ctx.permissions),
    )
