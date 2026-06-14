import pytest
from httpx import AsyncClient

from app.auth.middleware import auth_rate_limiter
from app.config import Settings


@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "auth_rate_limit_max_requests", 2)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    auth_rate_limiter.reset()

    for _ in range(2):
        response = await client.get("/api/v1/auth/login")
        assert response.status_code != 429

    response = await client.get("/api/v1/auth/login")
    assert response.status_code == 429
    assert response.json()["detail"] == "TOO_MANY_REQUESTS"


def test_rejects_weak_session_secret_in_production():
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        Settings(app_env="production", session_secret="change-me")


def test_accepts_strong_session_secret_in_production():
    settings = Settings(
        app_env="production",
        session_secret="a" * 32,
        zitadel_client_id="client",
        zitadel_client_secret="secret",
    )
    assert settings.session_secret == "a" * 32


@pytest.mark.asyncio
async def test_production_requires_zitadel_credentials():
    with pytest.raises(ValueError, match="ZITADEL_CLIENT_ID"):
        Settings(app_env="production", session_secret="a" * 32)
