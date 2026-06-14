"""JIT reconcile of Zitadel claims into Propel users and tenant memberships."""

import uuid

import pytest
from sqlalchemy import select

from app.auth.reconcile import reconcile_user_from_claims
from app.db.session import async_session_maker
from app.models.enums import MembershipStatus, Role
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import User


@pytest.mark.asyncio
async def test_reconcile_creates_tenant_and_owner_for_new_org(clean_db):
    """Model B: the first user of a granted org mints its tenant as owner."""
    org_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        user = await reconcile_user_from_claims(
            session,
            sub="zitadel-sub-1",
            email="owner@acme.com",
            email_verified=True,
            org_id=org_id,
            org_name="Acme Corp",
            name="Owner",
        )

        assert user.zitadel_user_id == "zitadel-sub-1"
        assert user.email == "owner@acme.com"
        assert user.name == "Owner"

        tenant = await session.scalar(
            select(Tenant).where(Tenant.zitadel_org_id == org_id)
        )
        assert tenant is not None
        assert tenant.name == "Acme Corp"

        membership = await session.scalar(
            select(TenantMembership).where(TenantMembership.user_id == user.id)
        )
        assert membership is not None
        assert membership.tenant_id == tenant.id
        assert membership.role == Role.owner
        assert membership.status == MembershipStatus.active


@pytest.mark.asyncio
async def test_reconcile_maps_project_role_for_subsequent_member(clean_db):
    """A second user joins an existing org-tenant with the granted project role."""
    org_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        await reconcile_user_from_claims(
            session,
            sub="zitadel-owner",
            email="owner@beta.com",
            email_verified=True,
            org_id=org_id,
            org_name="Beta LLC",
        )

        member = await reconcile_user_from_claims(
            session,
            sub="zitadel-member",
            email="member@beta.com",
            email_verified=True,
            org_id=org_id,
            org_name="Beta LLC",
            roles={"admin": {org_id: "beta.com"}},
        )

        membership = await session.scalar(
            select(TenantMembership).where(TenantMembership.user_id == member.id)
        )
        assert membership is not None
        assert membership.role == Role.admin
        assert membership.status == MembershipStatus.active

        # Exactly one tenant for the org (the second login reused it).
        tenants = (
            await session.scalars(select(Tenant).where(Tenant.zitadel_org_id == org_id))
        ).all()
        assert len(tenants) == 1


@pytest.mark.asyncio
async def test_reconcile_defaults_to_member_without_role_claim(clean_db):
    """A subsequent user with no project-role claim falls back to member."""
    org_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        await reconcile_user_from_claims(
            session,
            sub="zitadel-owner-2",
            email="owner@gamma.com",
            email_verified=True,
            org_id=org_id,
            org_name="Gamma",
        )

        member = await reconcile_user_from_claims(
            session,
            sub="zitadel-member-2",
            email="member@gamma.com",
            email_verified=True,
            org_id=org_id,
            org_name="Gamma",
        )

        membership = await session.scalar(
            select(TenantMembership).where(TenantMembership.user_id == member.id)
        )
        assert membership is not None
        assert membership.role == Role.member


@pytest.mark.asyncio
async def test_reconcile_links_existing_user_by_email(clean_db):
    org_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        existing = User(email="dev@acme.com", email_verified=True, name="Dev")
        session.add(existing)
        await session.commit()

        user = await reconcile_user_from_claims(
            session,
            sub="zitadel-sub-2",
            email="dev@acme.com",
            email_verified=True,
            org_id=org_id,
            org_name="Acme",
        )

        assert user.id == existing.id
        assert user.zitadel_user_id == "zitadel-sub-2"


@pytest.mark.asyncio
async def test_reconcile_activates_invited_membership(clean_db):
    async with async_session_maker() as session:
        tenant = Tenant(name="Acme", slug="acme-invite")
        session.add(tenant)
        await session.flush()
        user = User(email="invitee@acme.com", email_verified=True)
        session.add(user)
        await session.flush()
        session.add(
            TenantMembership(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.member,
                status=MembershipStatus.invited,
            )
        )
        await session.commit()

        await reconcile_user_from_claims(
            session,
            sub="zitadel-sub-3",
            email="invitee@acme.com",
            email_verified=True,
            org_id=None,
            org_name=None,
        )

        membership = await session.scalar(
            select(TenantMembership).where(TenantMembership.user_id == user.id)
        )
        assert membership.status == MembershipStatus.active


@pytest.mark.asyncio
async def test_reconcile_attaches_membership_to_existing_org_tenant(clean_db):
    """An org provisioned for enterprise SSO (tenant has zitadel_org_id) gets the
    logging-in user attached as a member; first member becomes owner."""
    org_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        tenant = Tenant(name="Acme", slug="acme-sso", zitadel_org_id=org_id)
        session.add(tenant)
        await session.commit()

        user = await reconcile_user_from_claims(
            session,
            sub="zitadel-sub-4",
            email="first@acme.com",
            email_verified=True,
            org_id=org_id,
            org_name="Acme",
        )

        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.user_id == user.id,
            )
        )
        assert membership is not None
        assert membership.role == Role.owner
        assert membership.status == MembershipStatus.active


@pytest.mark.asyncio
async def test_reconcile_links_pending_github_identity_by_email(clean_db):
    from app.models.connected_account import ConnectedAccount
    from app.models.enums import (
        AuthType,
        GitHubOrgRole,
        IdentityStatus,
        IntegrationProvider,
    )
    from app.models.external_identity import ExternalIdentity

    org_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        tenant = Tenant(name="Acme", slug="acme-github", zitadel_org_id=org_id)
        session.add(tenant)
        await session.flush()
        account = ConnectedAccount(
            tenant_id=tenant.id,
            provider=IntegrationProvider.github.value,
            auth_type=AuthType.github_app_installation.value,
            external_account_id="123",
            external_account_name="acme",
        )
        session.add(account)
        await session.flush()
        session.add(
            ExternalIdentity(
                tenant_id=tenant.id,
                connected_account_id=account.id,
                provider=IntegrationProvider.github.value,
                external_user_id="42",
                external_login="dev",
                external_email="dev@acme.com",
                github_org_role=GitHubOrgRole.admin.value,
                status=IdentityStatus.pending_email.value,
            )
        )
        await session.commit()

        user = await reconcile_user_from_claims(
            session,
            sub="zitadel-sub-github",
            email="dev@acme.com",
            email_verified=True,
            org_id=org_id,
            org_name="Acme",
        )

        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant.id,
                TenantMembership.user_id == user.id,
            )
        )
        assert membership is not None
        assert membership.role == Role.owner
