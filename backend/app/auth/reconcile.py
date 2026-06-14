"""JIT reconciliation of Zitadel identity claims into Propel Postgres."""

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MembershipStatus, Role
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User
from app.services.role_permissions import default_permission_rows

logger = logging.getLogger("propel.auth.reconcile")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug[:60] or "workspace"


async def reconcile_user_from_claims(
    session: AsyncSession,
    *,
    sub: str,
    email: str,
    email_verified: bool,
    org_id: str | None,
    org_name: str | None,
    name: str | None = None,
) -> User:
    """Upsert app_user and ensure tenant membership for the token's org."""
    result = await session.execute(select(User).where(User.zitadel_user_id == sub))
    user = result.scalar_one_or_none()

    if user is None:
        by_email = await session.execute(select(User).where(User.email == email))
        user = by_email.scalar_one_or_none()

    if user is None:
        user = User(
            zitadel_user_id=sub,
            email=email,
            email_verified=email_verified,
            name=name,
        )
        session.add(user)
    else:
        user.zitadel_user_id = sub
        user.email = email
        user.email_verified = email_verified
        if name and not user.name:
            user.name = name

    await session.flush()

    if org_id:
        await _ensure_org_membership(
            session,
            user=user,
            org_id=org_id,
            org_name=org_name or email.split("@")[-1],
        )

    await _activate_invited_memberships(session, user)
    await session.commit()
    await session.refresh(user)
    return user


async def _ensure_org_membership(
    session: AsyncSession,
    *,
    user: User,
    org_id: str,
    org_name: str,
) -> TenantMembership:
    tenant_result = await session.execute(
        select(Tenant).where(Tenant.zitadel_org_id == org_id)
    )
    tenant = tenant_result.scalar_one_or_none()

    if tenant is None:
        slug = await _unique_slug(session, _slugify(org_name))
        tenant = Tenant(name=org_name, slug=slug, zitadel_org_id=org_id)
        session.add(tenant)
        await session.flush()
        session.add_all(default_permission_rows(tenant.id))

    membership_result = await session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant.id,
            TenantMembership.user_id == user.id,
        )
    )
    membership = membership_result.scalar_one_or_none()

    if membership is None:
        role = Role.owner if tenant.zitadel_org_id == org_id else Role.member
        # First member of a new tenant is owner.
        existing = await session.execute(
            select(TenantMembership.id).where(TenantMembership.tenant_id == tenant.id)
        )
        if existing.first() is None:
            role = Role.owner
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=role,
            status=MembershipStatus.active,
        )
        session.add(membership)
    elif membership.status == MembershipStatus.invited:
        membership.status = MembershipStatus.active

    return membership


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = base
    suffix = 1
    while True:
        existing = await session.execute(select(Tenant.id).where(Tenant.slug == slug))
        if existing.scalar_one_or_none() is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


async def _activate_invited_memberships(session: AsyncSession, user: User) -> None:
    """Flip invited memberships to active when the user's email matches."""
    result = await session.execute(
        select(TenantMembership)
        .join(User, TenantMembership.user_id == User.id)
        .where(
            User.id == user.id,
            TenantMembership.status == MembershipStatus.invited,
        )
    )
    for membership in result.scalars():
        membership.status = MembershipStatus.active


async def create_test_user(
    session: AsyncSession,
    *,
    email: str,
    zitadel_user_id: str | None = None,
    name: str | None = "Test User",
) -> User:
    """Create a user for integration tests (APP_ENV=test only)."""
    sub = zitadel_user_id or str(uuid.uuid4())
    user = User(
        zitadel_user_id=sub,
        email=email,
        email_verified=True,
        name=name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
