"""Map ingested GitHub org members onto Propel users.

Reads the org roster + user profiles that the ingestion pipeline landed in
`raw_record`, upserts an `external_identities` row per GitHub member, then links
each identity to a Propel user (or auto-provisions one) and reconciles tenant
membership roles from the member's GitHub org role.

Linking is intentionally conservative: only a matching GitHub login-OAuth account
id or an exact email auto-links to an existing user. Everything else is either
auto-provisioned (when we know the member's email) or parked as `pending_email`
until the member signs in with GitHub.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    GitHubOrgRole,
    IdentityLinkMethod,
    IdentityStatus,
    IntegrationProvider,
    Role,
)
from app.models.external_identity import ExternalIdentity
from app.models.membership import TenantMembership
from app.models.raw_record import RawRecord
from app.models.user import OAuthAccount, User
from app.services import members as member_service

logger = logging.getLogger("propel.ingestion")

_GITHUB = IntegrationProvider.github.value
_ORG_MEMBERS_RESOURCE = "organization_members"
_USER_PROFILES_RESOURCE = "users"
_password_helper = PasswordHelper()


@dataclass
class RosterEntry:
    external_user_id: str
    login: str
    email: str | None
    name: str | None
    org_role: str
    metadata: dict


async def sync_and_link(
    session: AsyncSession,
    account: ConnectedAccount,
    *,
    admin_logins: set[str],
) -> None:
    """Full reconciliation pass for one connected account."""
    roster = await _build_roster(session, account, admin_logins=admin_logins)
    if not roster:
        logger.info("No GitHub org members to reconcile for account %s", account.id)
        return

    await _upsert_identities(session, account, roster)
    await session.commit()

    await _link_and_provision(session, account)
    await _reconcile_roles(session, account)
    await session.commit()


async def _build_roster(
    session: AsyncSession,
    account: ConnectedAccount,
    *,
    admin_logins: set[str],
) -> list[RosterEntry]:
    members = await _latest_payloads(session, account.tenant_id, _ORG_MEMBERS_RESOURCE)
    profiles = await _latest_payloads(
        session, account.tenant_id, _USER_PROFILES_RESOURCE
    )

    roster: list[RosterEntry] = []
    for login, member in members.items():
        if member.get("id") is None:
            continue
        profile = profiles.get(login, {})
        org_role = (
            GitHubOrgRole.admin.value
            if login in admin_logins
            else GitHubOrgRole.member.value
        )
        roster.append(
            RosterEntry(
                external_user_id=str(member["id"]),
                login=login,
                email=(profile.get("email") or None),
                name=(profile.get("name") or None),
                org_role=org_role,
                metadata={
                    "avatar_url": member.get("avatar_url"),
                    "site_admin": member.get("site_admin"),
                    "html_url": member.get("html_url"),
                },
            )
        )
    return roster


async def _latest_payloads(
    session: AsyncSession, tenant_id: uuid.UUID, resource_type: str
) -> dict[str, dict]:
    """Most recent raw payload per `login` for a resource type (newest wins)."""
    result = await session.execute(
        select(RawRecord.payload)
        .where(
            RawRecord.tenant_id == tenant_id,
            RawRecord.resource_type == resource_type,
        )
        .order_by(RawRecord.fetched_at.asc())
    )
    payloads: dict[str, dict] = {}
    for (payload,) in result.all():
        login = payload.get("login")
        if login:
            payloads[str(login)] = payload
    return payloads


async def _upsert_identities(
    session: AsyncSession,
    account: ConnectedAccount,
    roster: list[RosterEntry],
) -> None:
    existing = await _identities_by_user_id(session, account.tenant_id)
    now = datetime.now(UTC)
    for entry in roster:
        identity = existing.get(entry.external_user_id)
        if identity is None:
            identity = ExternalIdentity(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                provider=_GITHUB,
                external_user_id=entry.external_user_id,
                status=IdentityStatus.pending_email.value,
            )
            session.add(identity)
        identity.external_login = entry.login
        identity.external_email = entry.email
        identity.external_name = entry.name
        identity.github_org_role = entry.org_role
        identity.meta = entry.metadata
        identity.last_synced_at = now


async def _identities_by_user_id(
    session: AsyncSession, tenant_id: uuid.UUID
) -> dict[str, ExternalIdentity]:
    result = await session.execute(
        select(ExternalIdentity).where(
            ExternalIdentity.tenant_id == tenant_id,
            ExternalIdentity.provider == _GITHUB,
        )
    )
    return {i.external_user_id: i for i in result.scalars().all()}


async def _link_and_provision(session: AsyncSession, account: ConnectedAccount) -> None:
    result = await session.execute(
        select(ExternalIdentity).where(
            ExternalIdentity.tenant_id == account.tenant_id,
            ExternalIdentity.provider == _GITHUB,
            ExternalIdentity.propel_user_id.is_(None),
        )
    )
    for identity in result.scalars().all():
        user_id = await _match_oauth_id(session, identity.external_user_id)
        method = IdentityLinkMethod.oauth_id
        if user_id is None and identity.external_email:
            user_id = await _match_email(session, identity.external_email)
            method = IdentityLinkMethod.email

        if user_id is not None:
            if await _user_already_linked(session, account.tenant_id, user_id):
                logger.warning(
                    "User %s already linked to another GitHub identity in tenant "
                    "%s; leaving %s unlinked",
                    user_id,
                    account.tenant_id,
                    identity.external_login,
                )
                continue
            await _attach(session, account, identity, user_id, method)
            continue

        if identity.external_email:
            await _provision(session, account, identity)
        else:
            identity.status = IdentityStatus.pending_email.value


async def _match_oauth_id(
    session: AsyncSession, external_user_id: str
) -> uuid.UUID | None:
    return await session.scalar(
        select(OAuthAccount.user_id).where(
            OAuthAccount.oauth_name == _GITHUB,
            OAuthAccount.account_id == external_user_id,
        )
    )


async def _match_email(session: AsyncSession, email: str) -> uuid.UUID | None:
    return await session.scalar(
        select(User.id).where(func.lower(User.email) == email.lower())
    )


async def _user_already_linked(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    found = await session.scalar(
        select(ExternalIdentity.id).where(
            ExternalIdentity.tenant_id == tenant_id,
            ExternalIdentity.provider == _GITHUB,
            ExternalIdentity.propel_user_id == user_id,
        )
    )
    return found is not None


async def _attach(
    session: AsyncSession,
    account: ConnectedAccount,
    identity: ExternalIdentity,
    user_id: uuid.UUID,
    method: IdentityLinkMethod,
) -> None:
    identity.propel_user_id = user_id
    identity.link_method = method.value
    identity.status = IdentityStatus.linked.value
    identity.linked_at = datetime.now(UTC)
    await _ensure_membership(
        session, account.tenant_id, user_id, _propel_role(identity.github_org_role)
    )


async def _provision(
    session: AsyncSession,
    account: ConnectedAccount,
    identity: ExternalIdentity,
) -> None:
    user = User(
        email=identity.external_email.lower(),
        name=identity.external_name,
        # Unusable password: provisioned users sign in via GitHub OAuth (or a
        # future invite/reset flow), never with this hash.
        hashed_password=_password_helper.hash(secrets.token_urlsafe(32)),
        is_active=True,
        is_verified=False,
    )
    session.add(user)
    await session.flush()

    identity.propel_user_id = user.id
    identity.link_method = IdentityLinkMethod.provisioned.value
    identity.status = IdentityStatus.provisioned.value
    identity.linked_at = datetime.now(UTC)
    await _ensure_membership(
        session, account.tenant_id, user.id, _propel_role(identity.github_org_role)
    )


async def _ensure_membership(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
) -> None:
    existing = await session.scalar(
        select(TenantMembership).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == user_id,
        )
    )
    if existing is None:
        session.add(TenantMembership(tenant_id=tenant_id, user_id=user_id, role=role))


async def _reconcile_roles(session: AsyncSession, account: ConnectedAccount) -> None:
    """Promote/demote linked members to match their GitHub org role.

    GitHub is the source of truth, except the last Propel admin is never demoted.
    Only admin↔individual transitions are driven here; a manually-set `manager`
    is left untouched when GitHub reports a plain member.
    """
    result = await session.execute(
        select(ExternalIdentity, TenantMembership)
        .join(
            TenantMembership,
            (TenantMembership.tenant_id == ExternalIdentity.tenant_id)
            & (TenantMembership.user_id == ExternalIdentity.propel_user_id),
        )
        .where(
            ExternalIdentity.tenant_id == account.tenant_id,
            ExternalIdentity.provider == _GITHUB,
            ExternalIdentity.propel_user_id.is_not(None),
        )
    )
    for identity, membership in result.all():
        desired = _propel_role(identity.github_org_role)
        if desired == Role.admin and membership.role != Role.admin:
            membership.role = Role.admin
        elif (
            identity.github_org_role == GitHubOrgRole.member.value
            and membership.role == Role.admin
        ):
            admin_count = await member_service.count_admins(session, account.tenant_id)
            if admin_count <= 1:
                logger.warning(
                    "Not demoting %s: would remove the last admin in tenant %s",
                    identity.external_login,
                    account.tenant_id,
                )
                continue
            membership.role = Role.individual


def _propel_role(org_role: str | None) -> Role:
    if org_role == GitHubOrgRole.admin.value:
        return Role.admin
    return Role.individual


async def link_oauth_identity(
    session: AsyncSession, user_id: uuid.UUID, external_user_id: str
) -> None:
    """Retroactively claim pending GitHub identities for a user that just signed in.

    Called after a GitHub login-OAuth account is established. Links every pending
    identity (across tenants) whose GitHub user id matches, then ensures the
    member's tenant membership and role.
    """
    result = await session.execute(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == _GITHUB,
            ExternalIdentity.external_user_id == external_user_id,
            ExternalIdentity.propel_user_id.is_(None),
        )
    )
    identities = list(result.scalars().all())
    if not identities:
        return

    for identity in identities:
        if await _user_already_linked(session, identity.tenant_id, user_id):
            continue
        identity.propel_user_id = user_id
        identity.link_method = IdentityLinkMethod.oauth_id.value
        identity.status = IdentityStatus.linked.value
        identity.linked_at = datetime.now(UTC)
        await _ensure_membership(
            session,
            identity.tenant_id,
            user_id,
            _propel_role(identity.github_org_role),
        )
    await session.commit()


async def list_identities(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[ExternalIdentity]:
    result = await session.execute(
        select(ExternalIdentity)
        .where(
            ExternalIdentity.tenant_id == tenant_id,
            ExternalIdentity.provider == _GITHUB,
        )
        .order_by(ExternalIdentity.external_login.asc())
    )
    return list(result.scalars().all())


async def _get_identity(
    session: AsyncSession, tenant_id: uuid.UUID, identity_id: uuid.UUID
) -> ExternalIdentity:
    identity = await session.scalar(
        select(ExternalIdentity).where(
            ExternalIdentity.id == identity_id,
            ExternalIdentity.tenant_id == tenant_id,
            ExternalIdentity.provider == _GITHUB,
        )
    )
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found"
        )
    return identity


async def manual_link(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    identity_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ExternalIdentity:
    """Admin override: attach a GitHub identity to an existing Propel user."""
    identity = await _get_identity(session, tenant_id, identity_id)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if await _user_already_linked(session, tenant_id, user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already linked to a GitHub identity in this tenant",
        )
    identity.propel_user_id = user_id
    identity.link_method = IdentityLinkMethod.manual.value
    identity.status = IdentityStatus.linked.value
    identity.linked_at = datetime.now(UTC)
    await _ensure_membership(
        session, tenant_id, user_id, _propel_role(identity.github_org_role)
    )
    await session.commit()
    await session.refresh(identity)
    return identity


async def manual_unlink(
    session: AsyncSession, tenant_id: uuid.UUID, identity_id: uuid.UUID
) -> ExternalIdentity:
    """Detach a GitHub identity from its Propel user (membership is left intact)."""
    identity = await _get_identity(session, tenant_id, identity_id)
    identity.propel_user_id = None
    identity.link_method = None
    identity.linked_at = None
    identity.status = IdentityStatus.pending_email.value
    await session.commit()
    await session.refresh(identity)
    return identity
