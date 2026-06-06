import pytest
from httpx import AsyncClient

from app.auth.middleware import auth_rate_limiter
from app.config import Settings
from tests.conftest import auth_headers, login_user, register_user


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter():
    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "REGISTER_INVALID_PASSWORD"


@pytest.mark.asyncio
async def test_register_disabled_returns_403(client: AsyncClient, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "auth_registration_enabled", False)
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "blocked@example.com", "password": "testpass123"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "REGISTRATION_DISABLED"


@pytest.mark.asyncio
async def test_login_rate_limited(client: AsyncClient, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 3)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)

    await register_user(client, "limit@example.com")

    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "limit@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 400

    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "limit@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 429
    assert response.json()["detail"] == "TOO_MANY_REQUESTS"


def test_rejects_weak_jwt_secret_in_production():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(app_env="production", jwt_secret="change-me")


def test_accepts_strong_jwt_secret_in_production():
    settings = Settings(
        app_env="production",
        jwt_secret="a" * 32,
    )
    assert settings.jwt_secret == "a" * 32
