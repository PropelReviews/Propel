"""JIT reconciliation of Zitadel identity claims into Propel Postgres.

Model B (Zitadel-native multi-tenancy): every customer is a Zitadel
*organization* that has been granted the Propel project. When a user logs in,
their token carries the resource-owner org (``urn:zitadel:iam:org:id``) and the
project roles granted to them (``urn:zitadel:iam:org:project:roles``). We
mirror that org into a Propel ``Tenant`` and the granted role into a
``TenantMembership`` so the rest of the app keeps working off local rows.
"""

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MembershipStatus, Role
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User
from app.services import github_identity
from app.services.role_permissions import default_permission_rows

logger = logging.getLogger("propel.auth.reconcile")

_SLUG_RE = re.compile(r"[^a-z0-9]+")

# Zitadel project-role keys -> Propel membership role. Roles are configured on
# the Propel project in zitadel_bootstrap.py; anything unrecognised falls back
# to the least-privileged member role.
_ROLE_MAP: dict[str, Role] = {
    "owner": Role.owner,
    "admin": Role.admin,
    "manager": Role.manager,
    "member": Role.member,
}
# Highest-privilege first, for picking a single role when several are granted.
_ROLE_PRECEDENCE: tuple[Role, ...] = (Role.owner, Role.admin, Role.manager, Role.member)


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    return slug[:60] or "workspace"


def _highest_role(role_keys: list[str]) -> Role | None:
    """Map Zitadel project-role keys to the strongest matching Propel role."""
    mapped = {_ROLE_MAP[key] for key in role_keys if key in _ROLE_MAP}
    for role in _ROLE_PRECEDENCE:
        if role in mapped:
            return role
    return None


def _extract_role_keys(roles: object) -> list[str]:
    """Normalise the ``urn:zitadel:iam:org:project:roles`` claim to role keys.

    Zitadel asserts this claim as ``{role_key: {org_id: org_domain}}`` but older
    configs / custom actions may emit a plain list of role keys. Accept both.
    """
    if isinstance(roles, dict):
        return [str(key) for key in roles]
    if isinstance(roles, list):
        return [str(key) for key in roles]
    return []


async def reconcile_user_from_claims(
    session: AsyncSession,
    *,
    sub: str,
    email: str,
    email_verified: bool,
    org_id: str | None,
    org_name: str | None = None,
    name: str | None = None,
    roles: object = None,
) -> User:
    """Upsert app_user and ensure tenant membership for the token's org.

    ``roles`` is the raw ``urn:zitadel:iam:org:project:roles`` claim and decides
    the membership role for the org's tenant. The first member of a freshly
    minted tenant always becomes owner (the onboarding admin).
    """
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
            granted_role=_highest_role(_extract_role_keys(roles)),
        )

    await _activate_invited_memberships(session, user)
    await github_identity.link_email_identity(session, user.id, user.email)
    await session.commit()
    await session.refresh(user)
    return user


async def _ensure_org_membership(
    session: AsyncSession,
    *,
    user: User,
    org_id: str,
    org_name: str,
    granted_role: Role | None,
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

    # First member of a tenant is always owner; otherwise honour the granted
    # project role, defaulting to member when the claim is absent.
    existing = await session.execute(
        select(TenantMembership.id).where(TenantMembership.tenant_id == tenant.id)
    )
    is_first_member = existing.first() is None
    role = Role.owner if is_first_member else (granted_role or Role.member)

    if membership is None:
        membership = TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role=role,
            status=MembershipStatus.active,
        )
        session.add(membership)
    else:
        if membership.status == MembershipStatus.invited:
            membership.status = MembershipStatus.active
        # Keep the local role in sync with Zitadel grants, but never demote the
        # founding owner away from owner via a weaker grant.
        if granted_role is not None and membership.role != Role.owner:
            membership.role = granted_role

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


async def get_or_create_test_user(
    session: AsyncSession,
    *,
    email: str,
    zitadel_user_id: str | None = None,
    name: str | None = "Test User",
) -> User:
    """Return an existing test user by email, or create one."""
    normalized = email.lower()
    result = await session.execute(select(User).where(User.email == normalized))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        zitadel_user_id=zitadel_user_id or str(uuid.uuid4()),
        email=normalized,
        email_verified=True,
        name=name,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# Backwards-compatible alias for callers that create users in tests.
create_test_user = get_or_create_test_user
