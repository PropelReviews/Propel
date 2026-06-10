from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_member, require_permission
from app.auth.manager import current_active_user
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.roles import TenantWithMembershipRead
from app.schemas.tenant import TenantCreate, TenantRead, TenantUpdate
from app.services import tenants as tenant_service

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


@router.post("/", response_model=TenantRead, status_code=201)
async def create_tenant(
    payload: TenantCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    tenant = await tenant_service.create_tenant(session, user, payload)
    return TenantRead.model_validate(tenant)


@router.get("/", response_model=list[TenantWithMembershipRead])
async def list_tenants(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    rows = await tenant_service.list_user_tenants_with_membership(session, user.id)
    return [
        TenantWithMembershipRead(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            created_at=tenant.created_at,
            role=role,
            permissions=sorted(permissions),
        )
        for tenant, role, permissions in rows
    ]


@router.get("/{tenant_id}", response_model=TenantRead)
async def get_tenant(ctx=Depends(require_member)):
    return TenantRead.model_validate(ctx.tenant)


@router.patch("/{tenant_id}", response_model=TenantRead)
async def update_tenant(
    payload: TenantUpdate,
    ctx=Depends(require_permission("tenant:update")),
    session: AsyncSession = Depends(get_async_session),
):
    tenant = await tenant_service.update_tenant(session, ctx.tenant, payload)
    return TenantRead.model_validate(tenant)


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(
    ctx=Depends(require_permission("tenant:delete")),
    session: AsyncSession = Depends(get_async_session),
):
    await tenant_service.soft_delete_tenant(session, ctx.tenant)
