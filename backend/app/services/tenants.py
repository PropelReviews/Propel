import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services import role_permissions as role_permission_service
from app.services.role_permissions import default_permission_rows


async def create_tenant(
    session: AsyncSession, user: User, payload: TenantCreate
) -> Tenant:
    tenant = Tenant(name=payload.name, slug=payload.slug)
    membership = TenantMembership(tenant=tenant, user_id=user.id, role=Role.admin)
    session.add(tenant)
    session.add(membership)
    try:
        await session.flush()
        session.add_all(default_permission_rows(tenant.id))
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists"
        ) from exc
    await session.refresh(tenant)
    return tenant


async def list_user_tenants(session: AsyncSession, user_id: uuid.UUID) -> list[Tenant]:
    result = await session.execute(
        select(Tenant)
        .join(TenantMembership)
        .where(
            TenantMembership.user_id == user_id,
            Tenant.deleted_at.is_(None),
        )
        .order_by(Tenant.created_at.desc())
    )
    return list(result.scalars().unique().all())


async def list_user_tenants_with_membership(
    session: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Tenant, Role, set[str]]]:
    """Tenants the user belongs to, with their role + effective permissions."""
    result = await session.execute(
        select(Tenant, TenantMembership.role)
        .join(TenantMembership)
        .where(
            TenantMembership.user_id == user_id,
            Tenant.deleted_at.is_(None),
        )
        .order_by(Tenant.created_at.desc())
    )
    pairs = [(tenant, role) for tenant, role in result.unique().all()]
    return [
        (
            tenant,
            role,
            await role_permission_service.get_effective_permissions(
                session, tenant.id, role
            ),
        )
        for tenant, role in pairs
    ]


async def update_tenant(
    session: AsyncSession, tenant: Tenant, payload: TenantUpdate
) -> Tenant:
    if payload.name is not None:
        tenant.name = payload.name
    if payload.slug is not None:
        tenant.slug = payload.slug
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists"
        ) from exc
    await session.refresh(tenant)
    return tenant


async def soft_delete_tenant(session: AsyncSession, tenant: Tenant) -> None:
    tenant.deleted_at = datetime.now(UTC)
    await session.commit()
