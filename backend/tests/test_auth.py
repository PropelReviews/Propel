import pytest
from httpx import AsyncClient
from tests.conftest import auth_headers, login_user, register_user


@pytest.mark.asyncio
async def test_register_login_and_me(client: AsyncClient):
    await register_user(client, "alice@example.com")
    token = await login_user(client, "alice@example.com")

    me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Test User"
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client: AsyncClient):
    await register_user(client, "bob@example.com")
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "bob@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_jwt_rejection(client: AsyncClient):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401
