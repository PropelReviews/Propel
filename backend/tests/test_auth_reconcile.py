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
async def test_reconcile_creates_user_and_owner_membership_for_new_org(clean_db):
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
        assert tenant.slug == "acme-corp"

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
async def test_reconcile_picks_unique_slug_when_taken(clean_db):
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    async with async_session_maker() as session:
        session.add(Tenant(name="Acme", slug="acme", zitadel_org_id=org_a))
        await session.commit()

        await reconcile_user_from_claims(
            session,
            sub="zitadel-sub-4",
            email="second@acme.com",
            email_verified=True,
            org_id=org_b,
            org_name="Acme",
        )

        tenant = await session.scalar(
            select(Tenant).where(Tenant.zitadel_org_id == org_b)
        )
        assert tenant.slug == "acme-1"
