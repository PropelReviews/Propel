import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role
from app.models.membership import TenantMembership
from app.models.user import User
from app.schemas.membership import MemberRead, MemberRoleUpdate


async def count_admins(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(TenantMembership)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.role == Role.admin,
        )
    )
    return int(result.scalar_one())


async def list_members(session: AsyncSession, tenant_id: uuid.UUID) -> list[MemberRead]:
    result = await session.execute(
        select(TenantMembership, User)
        .join(User, TenantMembership.user_id == User.id)
        .where(TenantMembership.tenant_id == tenant_id)
        .order_by(TenantMembership.created_at.asc())
    )
    return [
        MemberRead(
            user_id=user.id,
            email=user.email,
            name=user.name,
            role=membership.role,
            created_at=membership.created_at,
        )
        for membership, user in result.all()
    ]


async def assign_role(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    target_user_id: uuid.UUID,
    payload: MemberRoleUpdate,
) -> MemberRead:
    result = await session.execute(
        select(TenantMembership, User)
        .join(User, TenantMembership.user_id == User.id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == target_user_id,
        )
    )
    row = result.one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )

    membership, user = row
    if membership.role == Role.admin and payload.role != Role.admin:
        admin_count = await count_admins(session, tenant_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last admin",
            )

    membership.role = payload.role
    await session.commit()
    await session.refresh(membership)
    return MemberRead(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=membership.role,
        created_at=membership.created_at,
    )


async def remove_member(
    session: AsyncSession, tenant_id: uuid.UUID, target_user_id: uuid.UUID
) -> None:
    result = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == target_user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Member not found"
        )

    if membership.role == Role.admin:
        admin_count = await count_admins(session, tenant_id)
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last admin",
            )

    await session.delete(membership)
    await session.commit()
