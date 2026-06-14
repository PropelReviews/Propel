import pytest
from httpx import AsyncClient
from tests.conftest import login_user, register_user


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
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "development")
    response = await client.post("/api/v1/auth/test/login", params={"email": "x@y.com"})
    assert response.status_code == 404
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "test")
