import pytest
from httpx import AsyncClient
from tests.conftest import auth_headers, create_tenant, login_user, register_user


async def _setup_tenant_with_roles(client: AsyncClient):
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

    await register_user(client, "member@example.com")
    member_token = await login_user(client, "member@example.com")
    mem_invite = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "member@example.com", "role": "individual"},
        headers=auth_headers(admin_token),
    )
    mem_token = mem_invite.json()["invite_url"].split("/")[-2]
    await client.post(
        f"/api/v1/invites/{mem_token}/accept",
        headers=auth_headers(member_token),
    )

    members = await client.get(
        f"/api/v1/tenants/{tenant['id']}/members/",
        headers=auth_headers(admin_token),
    )
    users = {m["email"]: m["user_id"] for m in members.json()}
    return tenant, admin_token, manager_token, member_token, users


@pytest.mark.asyncio
async def test_admin_can_assign_roles(client: AsyncClient):
    tenant, admin_token, _, _, users = await _setup_tenant_with_roles(client)

    updated = await client.patch(
        f"/api/v1/tenants/{tenant['id']}/members/{users['member@example.com']}/role",
        json={"role": "manager"},
        headers=auth_headers(admin_token),
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_manager_cannot_assign_roles(client: AsyncClient):
    tenant, _, manager_token, _, users = await _setup_tenant_with_roles(client)

    forbidden = await client.patch(
        f"/api/v1/tenants/{tenant['id']}/members/{users['member@example.com']}/role",
        json={"role": "admin"},
        headers=auth_headers(manager_token),
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_last_admin_guard_on_remove(client: AsyncClient):
    tenant, admin_token, _, _, users = await _setup_tenant_with_roles(client)

    conflict = await client.delete(
        f"/api/v1/tenants/{tenant['id']}/members/{users['admin@example.com']}",
        headers=auth_headers(admin_token),
    )
    assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_last_admin_guard_on_demote(client: AsyncClient):
    tenant, admin_token, _, _, users = await _setup_tenant_with_roles(client)

    conflict = await client.patch(
        f"/api/v1/tenants/{tenant['id']}/members/{users['admin@example.com']}/role",
        json={"role": "manager"},
        headers=auth_headers(admin_token),
    )
    assert conflict.status_code == 409
