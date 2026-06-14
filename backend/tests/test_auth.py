import uuid

import pytest
from httpx import AsyncClient
from tests.conftest import auth_headers, login_user, register_user

from app.db.session import async_session_maker
from app.models.user import User


@pytest.mark.asyncio
async def test_me_requires_session(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_register_and_me(client: AsyncClient):
    await register_user(client, "alice@example.com")
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["email_verified"] is True


@pytest.mark.asyncio
async def test_logout_clears_session(client: AsyncClient):
    await login_user(client, "bob@example.com")
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    response = await client.get("/api/v1/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_test_login_disabled_outside_test_env(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth.get_settings",
        lambda: type("S", (), {"is_test_env": False})(),
    )
    response = await client.post("/api/v1/auth/test/login", params={"email": "x@y.com"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_test_login_is_idempotent_for_same_email(client: AsyncClient):
    first = await register_user(client, "repeat@example.com")
    second = await login_user(client, "repeat@example.com")
    assert first["id"] == second


@pytest.mark.asyncio
async def test_test_login_normalizes_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/test/login",
        params={"email": "Mixed@Example.COM"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "mixed@example.com"


@pytest.mark.asyncio
async def test_me_rejects_inactive_user(client: AsyncClient):
    user_id = await login_user(client, "inactive@example.com")
    async with async_session_maker() as session:
        user = await session.get(User, uuid.UUID(user_id))
        user.is_active = False
        await session.commit()

    response = await client.get("/api/v1/auth/me", headers=auth_headers(user_id))
    assert response.status_code == 401
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_invalid_session_cookie(client: AsyncClient):
    client.cookies.set("propel_session", "not-a-valid-session")
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
