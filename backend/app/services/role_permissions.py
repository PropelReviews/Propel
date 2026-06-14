import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import (
    ALL_PERMISSION_KEYS,
    DEFAULT_ROLE_PERMISSIONS,
    LOCKED_OWNER_PERMISSIONS,
    PERMISSION_CATALOG,
)
from app.models.enums import Role
from app.models.role_permission import TenantRolePermission


def default_permission_rows(tenant_id: uuid.UUID) -> list[TenantRolePermission]:
    """Default grant rows for a new tenant (caller adds + commits)."""
    return [
        TenantRolePermission(tenant_id=tenant_id, role=role, permission=permission)
        for role, permissions in DEFAULT_ROLE_PERMISSIONS.items()
        for permission in sorted(permissions)
    ]


async def get_effective_permissions(
    session: AsyncSession, tenant_id: uuid.UUID, role: Role
) -> set[str]:
    """Permissions a role holds in a tenant.

    Tenants created before the permission table existed (no rows at all) fall
    back to the default matrix; a tenant with rows where this role has none
    genuinely has an empty grant set.
    """
    result = await session.execute(
        select(TenantRolePermission.role, TenantRolePermission.permission).where(
            TenantRolePermission.tenant_id == tenant_id
        )
    )
    rows = result.all()
    if not rows:
        return set(DEFAULT_ROLE_PERMISSIONS[role])
    return {permission for row_role, permission in rows if row_role == role}


async def get_all_role_permissions(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict[Role, set[str]]:
    """Effective permissions for every role in a tenant."""
    result = await session.execute(
        select(TenantRolePermission.role, TenantRolePermission.permission).where(
            TenantRolePermission.tenant_id == tenant_id
        )
    )
    rows = result.all()
    if not rows:
        return {role: set(perms) for role, perms in DEFAULT_ROLE_PERMISSIONS.items()}
    grants: dict[Role, set[str]] = {role: set() for role in Role}
    for role, permission in rows:
        grants[role].add(permission)
    return grants


async def set_role_permissions(
    session: AsyncSession, tenant_id: uuid.UUID, role: Role, permissions: list[str]
) -> set[str]:
    """Replace a role's permission grants with the given set."""
    requested = set(permissions)
    unknown = requested - ALL_PERMISSION_KEYS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown permissions: {', '.join(sorted(unknown))}",
        )
    if role == Role.owner:
        missing_locked = LOCKED_OWNER_PERMISSIONS - requested
        if missing_locked:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(f"Owner role must keep: {', '.join(sorted(missing_locked))}"),
            )

    result = await session.execute(
        select(TenantRolePermission).where(
            TenantRolePermission.tenant_id == tenant_id,
            TenantRolePermission.role == role,
        )
    )
    existing = {row.permission: row for row in result.scalars()}

    for permission, row in existing.items():
        if permission not in requested:
            await session.delete(row)
    for permission in requested - existing.keys():
        session.add(
            TenantRolePermission(tenant_id=tenant_id, role=role, permission=permission)
        )
    await session.commit()
    return requested


def catalog() -> list[dict[str, str]]:
    """Static permission catalog for the admin UI."""
    return [
        {
            "key": p.key,
            "label": p.label,
            "description": p.description,
            "group": p.group,
        }
        for p in PERMISSION_CATALOG
    ]
