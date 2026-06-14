"""GitHub org identity sync, linking, provisioning, and role reconciliation."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import auth_headers, create_tenant, login_user, register_user

from app.db.session import async_session_maker
from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    AuthType,
    GitHubOrgRole,
    IdentityLinkMethod,
    IdentityStatus,
    IntegrationProvider,
    Role,
)
from app.models.external_identity import ExternalIdentity
from app.models.membership import TenantMembership
from app.models.oauth_account import OAuthAccount
from app.models.raw_record import RawRecord
from app.models.tenant import Tenant
from app.models.user import User
from app.services import github_identity

_ORG = "acme"


async def _seed_account(session) -> ConnectedAccount:
    tenant = Tenant(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    account = ConnectedAccount(
        tenant_id=tenant.id,
        provider=IntegrationProvider.github.value,
        auth_type=AuthType.github_app_installation.value,
        external_account_id="42",
        external_account_name=_ORG,
    )
    session.add(account)
    await session.flush()
    return account


def _member(login: str, gid: int, *, site_admin: bool = False) -> RawRecord:
    return RawRecord(
        tenant_id=None,  # set by caller
        source="github",
        resource_type="organization_members",
        source_id=str(gid),
        payload={
            "org": _ORG,
            "login": login,
            "id": gid,
            "avatar_url": f"https://avatars/{login}",
            "site_admin": site_admin,
        },
    )


def _profile(login: str, gid: int, *, email: str | None, name: str | None) -> RawRecord:
    return RawRecord(
        tenant_id=None,
        source="github",
        resource_type="users",
        source_id=str(gid),
        payload={"login": login, "id": gid, "email": email, "name": name},
    )


async def _add_raw(session, tenant_id, *records: RawRecord) -> None:
    for record in records:
        record.tenant_id = tenant_id
        session.add(record)
    await session.flush()


@pytest.mark.asyncio
async def test_provisions_user_and_membership_for_unmatched_member(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        await _add_raw(
            session,
            account.tenant_id,
            _member("octocat", 1),
            _profile("octocat", 1, email="octocat@acme.com", name="The Octocat"),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins=set())

        identity = await session.scalar(
            select(ExternalIdentity).where(
                ExternalIdentity.tenant_id == account.tenant_id
            )
        )
        assert identity.status == IdentityStatus.provisioned.value
        assert identity.link_method == IdentityLinkMethod.provisioned.value
        assert identity.propel_user_id is not None

        user = await session.get(User, identity.propel_user_id)
        assert user.email == "octocat@acme.com"
        assert user.email_verified is False

        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == account.tenant_id,
                TenantMembership.user_id == user.id,
            )
        )
        assert membership.role == Role.member


@pytest.mark.asyncio
async def test_org_admin_provisions_as_propel_admin(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        await _add_raw(
            session,
            account.tenant_id,
            _member("owner", 2),
            _profile("owner", 2, email="owner@acme.com", name="Owner"),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins={"owner"})

        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "owner")
        )
        assert identity.github_org_role == GitHubOrgRole.admin.value
        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.user_id == identity.propel_user_id
            )
        )
        assert membership.role == Role.owner


@pytest.mark.asyncio
async def test_links_existing_user_by_email(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        user = User(email="dev@acme.com", is_active=True, email_verified=True)
        session.add(user)
        await session.flush()
        await _add_raw(
            session,
            account.tenant_id,
            _member("dev", 3),
            _profile("dev", 3, email="DEV@acme.com", name="Dev"),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins=set())

        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "dev")
        )
        assert identity.propel_user_id == user.id
        assert identity.link_method == IdentityLinkMethod.email.value
        assert identity.status == IdentityStatus.linked.value


@pytest.mark.asyncio
async def test_links_existing_user_by_oauth_id(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        user = User(email="gh@acme.com", is_active=True, email_verified=True)
        session.add(user)
        await session.flush()
        session.add(
            OAuthAccount(
                user_id=user.id,
                oauth_name="github",
                access_token="t",
                account_id="4",
                account_email="other@elsewhere.com",
            )
        )
        # No email on the profile, so only the oauth id can match.
        await _add_raw(
            session,
            account.tenant_id,
            _member("ghuser", 4),
            _profile("ghuser", 4, email=None, name="GH User"),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins=set())

        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "ghuser")
        )
        assert identity.propel_user_id == user.id
        assert identity.link_method == IdentityLinkMethod.oauth_id.value


@pytest.mark.asyncio
async def test_member_without_email_is_pending(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        await _add_raw(
            session,
            account.tenant_id,
            _member("ghost", 5),
            _profile("ghost", 5, email=None, name=None),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins=set())

        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "ghost")
        )
        assert identity.status == IdentityStatus.pending_email.value
        assert identity.propel_user_id is None
        users = (await session.execute(select(User))).scalars().all()
        assert users == []


@pytest.mark.asyncio
async def test_resync_is_idempotent(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        await _add_raw(
            session,
            account.tenant_id,
            _member("octocat", 1),
            _profile("octocat", 1, email="octocat@acme.com", name="The Octocat"),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins=set())
        await github_identity.sync_and_link(session, account, admin_logins=set())

        identities = (await session.execute(select(ExternalIdentity))).scalars().all()
        users = (await session.execute(select(User))).scalars().all()
        memberships = (await session.execute(select(TenantMembership))).scalars().all()
        assert len(identities) == 1
        assert len(users) == 1
        assert len(memberships) == 1


@pytest.mark.asyncio
async def test_last_admin_is_not_demoted(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        user = User(email="boss@acme.com", is_active=True, email_verified=True)
        session.add(user)
        await session.flush()
        session.add(
            TenantMembership(
                tenant_id=account.tenant_id, user_id=user.id, role=Role.owner
            )
        )
        session.add(
            ExternalIdentity(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                provider=IntegrationProvider.github.value,
                external_user_id="6",
                external_login="boss",
                propel_user_id=user.id,
                link_method=IdentityLinkMethod.email.value,
                status=IdentityStatus.linked.value,
                github_org_role=GitHubOrgRole.admin.value,
            )
        )
        # GitHub now reports "boss" as a plain member (not in admin_logins).
        await _add_raw(
            session,
            account.tenant_id,
            _member("boss", 6),
            _profile("boss", 6, email="boss@acme.com", name="Boss"),
        )
        await session.commit()

        await github_identity.sync_and_link(session, account, admin_logins=set())

        membership = await session.scalar(
            select(TenantMembership).where(TenantMembership.user_id == user.id)
        )
        assert membership.role == Role.owner


@pytest.mark.asyncio
async def test_retroactive_oauth_link_claims_pending_identity(clean_db):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        session.add(
            ExternalIdentity(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                provider=IntegrationProvider.github.value,
                external_user_id="7",
                external_login="late",
                status=IdentityStatus.pending_email.value,
                github_org_role=GitHubOrgRole.member.value,
            )
        )
        user = User(email="late@acme.com", is_active=True, email_verified=True)
        session.add(user)
        await session.flush()
        await session.commit()

        await github_identity.link_oauth_identity(session, user.id, "7")

        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "late")
        )
        assert identity.propel_user_id == user.id
        assert identity.status == IdentityStatus.linked.value
        membership = await session.scalar(
            select(TenantMembership).where(TenantMembership.user_id == user.id)
        )
        assert membership is not None


@pytest.mark.asyncio
async def test_register_claims_pending_identity_by_email(client: AsyncClient):
    async with async_session_maker() as session:
        account = await _seed_account(session)
        tenant_id = account.tenant_id
        session.add(
            ExternalIdentity(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                provider=IntegrationProvider.github.value,
                external_user_id="8",
                external_login="newhire",
                external_email="NewHire@acme.com",
                status=IdentityStatus.pending_email.value,
                github_org_role=GitHubOrgRole.admin.value,
            )
        )
        await session.commit()

    # Email match is case-insensitive; the org role maps to the Propel role.
    registered = await register_user(client, "newhire@ACME.com")

    async with async_session_maker() as session:
        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "newhire")
        )
        assert str(identity.propel_user_id) == registered["id"]
        assert identity.status == IdentityStatus.linked.value
        assert identity.link_method == IdentityLinkMethod.email.value
        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == identity.propel_user_id,
            )
        )
        assert membership is not None
        assert membership.role == Role.owner


@pytest.mark.asyncio
async def test_import_roster_from_github_api(clean_db, monkeypatch):
    from app.integrations.github import app_auth
    from app.integrations.github.app_auth import InstallationToken

    async def fake_token(installation_id: str):
        from datetime import UTC, datetime

        return InstallationToken(token="t", expires_at=datetime.now(UTC))

    async def fake_members(token: str, org: str):
        return [
            {"id": 1, "login": "boss", "avatar_url": "a", "site_admin": False},
            {"id": 2, "login": "dev", "avatar_url": "b", "site_admin": False},
        ]

    async def fake_admins(token: str, org: str):
        return {"boss"}

    monkeypatch.setattr(app_auth, "get_installation_token", fake_token)
    monkeypatch.setattr(app_auth, "list_org_members", fake_members)
    monkeypatch.setattr(app_auth, "list_org_admin_logins", fake_admins)

    async with async_session_maker() as session:
        account = await _seed_account(session)
        tenant_id = account.tenant_id
        await session.commit()

        count = await github_identity.import_roster_for_account(session, account)
        assert count == 2

        identities = {
            i.external_login: i
            for i in (
                await session.execute(
                    select(ExternalIdentity).where(
                        ExternalIdentity.tenant_id == tenant_id
                    )
                )
            ).scalars()
        }
    assert identities["boss"].github_org_role == GitHubOrgRole.admin.value
    assert identities["dev"].github_org_role == GitHubOrgRole.member.value
    # No emails from the members API: identities wait for signup or profile sync.
    assert identities["dev"].status == IdentityStatus.pending_email.value
    assert identities["dev"].propel_user_id is None


@pytest.mark.asyncio
async def test_admin_can_list_and_manually_link_github_members(client: AsyncClient):
    await register_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    async with async_session_maker() as session:
        account = ConnectedAccount(
            tenant_id=uuid.UUID(tenant["id"]),
            provider=IntegrationProvider.github.value,
            auth_type=AuthType.github_app_installation.value,
            external_account_id="99",
            external_account_name=_ORG,
        )
        session.add(account)
        await session.flush()
        session.add(
            ExternalIdentity(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                provider=IntegrationProvider.github.value,
                external_user_id="100",
                external_login="unlinked",
                external_email="unlinked@acme.com",
                status=IdentityStatus.pending_email.value,
                github_org_role=GitHubOrgRole.member.value,
            )
        )
        await session.commit()
        identity_id = await session.scalar(
            select(ExternalIdentity.id).where(
                ExternalIdentity.external_login == "unlinked"
            )
        )

    listing = await client.get(
        f"/api/v1/tenants/{tenant['id']}/github-members/",
        headers=auth_headers(admin_token),
    )
    assert listing.status_code == 200
    assert listing.json()[0]["external_login"] == "unlinked"

    me = await client.get("/api/v1/auth/me", headers=auth_headers(admin_token))
    admin_user_id = me.json()["id"]

    linked = await client.patch(
        f"/api/v1/tenants/{tenant['id']}/github-members/{identity_id}/link",
        json={"user_id": admin_user_id},
        headers=auth_headers(admin_token),
    )
    assert linked.status_code == 200
    assert linked.json()["status"] == IdentityStatus.linked.value
    assert linked.json()["link_method"] == IdentityLinkMethod.manual.value

    unlinked = await client.delete(
        f"/api/v1/tenants/{tenant['id']}/github-members/{identity_id}/link",
        headers=auth_headers(admin_token),
    )
    assert unlinked.status_code == 200
    assert unlinked.json()["propel_user_id"] is None
