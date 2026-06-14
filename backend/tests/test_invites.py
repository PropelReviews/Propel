from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import auth_headers, create_tenant, login_user, register_user

from app.db.session import async_session_maker
from app.models.invite import TenantInvite


@pytest.mark.asyncio
async def test_manager_can_invite_individual_not_admin(client: AsyncClient):
    await register_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    await register_user(client, "manager@example.com")
    manager_token = await login_user(client, "manager@example.com")
    mgr_invite = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "manager@example.com", "role": "manager"},
        headers=auth_headers(admin_token),
    )
    mgr_token = mgr_invite.json()["invite_url"].split("/")[-2]
    await client.post(
        f"/api/v1/invites/{mgr_token}/accept",
        headers=auth_headers(manager_token),
    )

    ok = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "newbie@example.com", "role": "member"},
        headers=auth_headers(manager_token),
    )
    assert ok.status_code == 201

    forbidden = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "admin2@example.com", "role": "admin"},
        headers=auth_headers(manager_token),
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_accept_invite_creates_membership(client: AsyncClient):
    await register_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    await register_user(client, "invitee@example.com")
    invitee_token = await login_user(client, "invitee@example.com")

    created = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "invitee@example.com", "role": "member"},
        headers=auth_headers(admin_token),
    )
    raw_token = created.json()["invite_url"].split("/")[-2]

    accepted = await client.post(
        f"/api/v1/invites/{raw_token}/accept",
        headers=auth_headers(invitee_token),
    )
    assert accepted.status_code == 200
    assert accepted.json()["tenant_id"] == tenant["id"]
    assert accepted.json()["role"] == "member"

    members = await client.get(
        f"/api/v1/tenants/{tenant['id']}/members/",
        headers=auth_headers(admin_token),
    )
    emails = {m["email"] for m in members.json()}
    assert "invitee@example.com" in emails


@pytest.mark.asyncio
async def test_expired_invite_rejected(client: AsyncClient):
    await register_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    await register_user(client, "late@example.com")
    late_token = await login_user(client, "late@example.com")

    created = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "late@example.com", "role": "member"},
        headers=auth_headers(admin_token),
    )
    raw_token = created.json()["invite_url"].split("/")[-2]

    async with async_session_maker() as session:
        result = await session.execute(select(TenantInvite))
        invite = result.scalar_one()
        invite.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await session.commit()

    expired = await client.post(
        f"/api/v1/invites/{raw_token}/accept",
        headers=auth_headers(late_token),
    )
    assert expired.status_code == 410
