import pytest
from httpx import AsyncClient
from tests.conftest import act_as_headers, create_tenant, login_test_user, login_user

from app.auth.permissions import DEFAULT_ROLE_PERMISSIONS
from app.models.enums import Role


async def _setup_admin_and_manager(client: AsyncClient):
    await login_test_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    await login_test_user(client, "manager@example.com")
    manager_token = await login_user(client, "manager@example.com")
    invite = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "manager@example.com", "role": "manager"},
        headers=act_as_headers(admin_token),
    )
    token = invite.json()["invite_url"].split("/")[-2]
    await client.post(
        f"/api/v1/invites/{token}/accept",
        headers=act_as_headers(manager_token),
    )
    return tenant, admin_token, manager_token


@pytest.mark.asyncio
async def test_new_tenant_gets_default_matrix(client: AsyncClient):
    await login_test_user(client, "owner@example.com")
    token = await login_user(client, "owner@example.com")
    tenant = await create_tenant(client, token)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/roles",
        headers=act_as_headers(token),
    )
    assert resp.status_code == 200
    grants = {row["role"]: set(row["permissions"]) for row in resp.json()}
    for role in Role:
        assert grants[role.value] == set(DEFAULT_ROLE_PERMISSIONS[role])


@pytest.mark.asyncio
async def test_tenant_list_includes_role_and_permissions(client: AsyncClient):
    await login_test_user(client, "owner@example.com")
    token = await login_user(client, "owner@example.com")
    await create_tenant(client, token)

    listed = await client.get("/api/v1/tenants/", headers=act_as_headers(token))
    assert listed.status_code == 200
    body = listed.json()
    assert body[0]["role"] == "owner"
    assert set(body[0]["permissions"]) == set(DEFAULT_ROLE_PERMISSIONS[Role.owner])


@pytest.mark.asyncio
async def test_membership_me(client: AsyncClient):
    tenant, _, manager_token = await _setup_admin_and_manager(client)

    resp = await client.get(
        f"/api/v1/tenants/{tenant['id']}/membership/me",
        headers=act_as_headers(manager_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "manager"
    assert set(body["permissions"]) == set(DEFAULT_ROLE_PERMISSIONS[Role.manager])


@pytest.mark.asyncio
async def test_admin_can_update_manager_permissions(client: AsyncClient):
    tenant, admin_token, manager_token = await _setup_admin_and_manager(client)

    # Revoke the manager's invite permissions.
    resp = await client.put(
        f"/api/v1/tenants/{tenant['id']}/roles/manager",
        json={"permissions": ["tenant:read", "members:read", "metrics:read"]},
        headers=act_as_headers(admin_token),
    )
    assert resp.status_code == 200
    assert set(resp.json()["permissions"]) == {
        "tenant:read",
        "members:read",
        "metrics:read",
    }

    # Manager can no longer create invites.
    denied = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "new@example.com", "role": "member"},
        headers=act_as_headers(manager_token),
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_manage_roles(client: AsyncClient):
    tenant, _, manager_token = await _setup_admin_and_manager(client)

    listed = await client.get(
        f"/api/v1/tenants/{tenant['id']}/roles",
        headers=act_as_headers(manager_token),
    )
    assert listed.status_code == 403

    updated = await client.put(
        f"/api/v1/tenants/{tenant['id']}/roles/member",
        json={"permissions": ["tenant:read"]},
        headers=act_as_headers(manager_token),
    )
    assert updated.status_code == 403


@pytest.mark.asyncio
async def test_locked_admin_permissions_cannot_be_removed(client: AsyncClient):
    await login_test_user(client, "owner@example.com")
    token = await login_user(client, "owner@example.com")
    tenant = await create_tenant(client, token)

    resp = await client.put(
        f"/api/v1/tenants/{tenant['id']}/roles/owner",
        json={"permissions": ["tenant:read"]},
        headers=act_as_headers(token),
    )
    assert resp.status_code == 422
    assert "Owner role must keep" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unknown_permission_rejected(client: AsyncClient):
    await login_test_user(client, "owner@example.com")
    token = await login_user(client, "owner@example.com")
    tenant = await create_tenant(client, token)

    resp = await client.put(
        f"/api/v1/tenants/{tenant['id']}/roles/member",
        json={"permissions": ["nope:invalid"]},
        headers=act_as_headers(token),
    )
    assert resp.status_code == 422
    assert "Unknown permissions" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_granting_invite_permission_expands_access(client: AsyncClient):
    """Custom grants override the legacy matrix: individuals can be allowed
    to invite individuals."""
    tenant, admin_token, _ = await _setup_admin_and_manager(client)

    await login_test_user(client, "member@example.com")
    member_token = await login_user(client, "member@example.com")
    invite = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "member@example.com", "role": "member"},
        headers=act_as_headers(admin_token),
    )
    token = invite.json()["invite_url"].split("/")[-2]
    await client.post(
        f"/api/v1/invites/{token}/accept", headers=act_as_headers(member_token)
    )

    # Individuals can't invite by default.
    denied = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "friend@example.com", "role": "member"},
        headers=act_as_headers(member_token),
    )
    assert denied.status_code == 403

    # Grant invites:role:member to the individual role.
    base = sorted(DEFAULT_ROLE_PERMISSIONS[Role.member])
    resp = await client.put(
        f"/api/v1/tenants/{tenant['id']}/roles/member",
        json={"permissions": [*base, "invites:role:member"]},
        headers=act_as_headers(admin_token),
    )
    assert resp.status_code == 200

    allowed = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "friend@example.com", "role": "member"},
        headers=act_as_headers(member_token),
    )
    assert allowed.status_code == 201

    # But still not managers.
    still_denied = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "boss@example.com", "role": "manager"},
        headers=act_as_headers(member_token),
    )
    assert still_denied.status_code == 403


@pytest.mark.asyncio
async def test_permission_catalog(client: AsyncClient):
    await login_test_user(client, "anyone@example.com")
    token = await login_user(client, "anyone@example.com")

    resp = await client.get(
        "/api/v1/permissions/catalog", headers=act_as_headers(token)
    )
    assert resp.status_code == 200
    body = resp.json()
    keys = {item["key"] for item in body}
    assert "roles:manage" in keys
    assert all({"key", "label", "description", "group"} <= set(i) for i in body)
