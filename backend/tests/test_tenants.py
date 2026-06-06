import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers, create_tenant, login_user, register_user


@pytest.mark.asyncio
async def test_create_tenant_makes_creator_admin(client: AsyncClient):
    await register_user(client, "owner@example.com")
    token = await login_user(client, "owner@example.com")
    tenant = await create_tenant(client, token, name="Propel Co", slug="propel-co")

    members = await client.get(
        f"/api/v1/tenants/{tenant['id']}/members/",
        headers=auth_headers(token),
    )
    assert members.status_code == 200
    body = members.json()
    assert len(body) == 1
    assert body[0]["email"] == "owner@example.com"
    assert body[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_list_tenants(client: AsyncClient):
    await register_user(client, "lister@example.com")
    token = await login_user(client, "lister@example.com")
    await create_tenant(client, token, name="One", slug="one")

    listed = await client.get("/api/v1/tenants/", headers=auth_headers(token))
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_soft_delete_admin_only(client: AsyncClient):
    await register_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    await register_user(client, "member@example.com")
    member_token = await login_user(client, "member@example.com")

    invite = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "member@example.com", "role": "individual"},
        headers=auth_headers(admin_token),
    )
    assert invite.status_code == 201
    token = invite.json()["invite_url"].split("/")[-2]
    accept = await client.post(
        f"/api/v1/invites/{token}/accept",
        headers=auth_headers(member_token),
    )
    assert accept.status_code == 200

    forbidden = await client.delete(
        f"/api/v1/tenants/{tenant['id']}",
        headers=auth_headers(member_token),
    )
    assert forbidden.status_code == 403

    deleted = await client.delete(
        f"/api/v1/tenants/{tenant['id']}",
        headers=auth_headers(admin_token),
    )
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/tenants/", headers=auth_headers(admin_token))
    assert listed.json() == []


@pytest.mark.asyncio
async def test_slug_conflict_returns_409(client: AsyncClient):
    await register_user(client, "slug@example.com")
    token = await login_user(client, "slug@example.com")
    await create_tenant(client, token, slug="taken")

    conflict = await client.post(
        "/api/v1/tenants/",
        json={"name": "Other", "slug": "taken"},
        headers=auth_headers(token),
    )
    assert conflict.status_code == 409
