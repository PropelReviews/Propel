"""OIDC BFF endpoints: login redirect, callback reconcile, logout."""

import types
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import login_user

from app.db.session import async_session_maker
from app.models.user import User


def _mock_zitadel_oauth(monkeypatch, auth_router, **methods):
    zitadel = types.SimpleNamespace(**methods)
    monkeypatch.setattr(auth_router, "oauth", types.SimpleNamespace(zitadel=zitadel))


@pytest.mark.asyncio
async def test_oidc_login_503_when_not_configured(client: AsyncClient):
    response = await client.get("/api/v1/auth/login")
    assert response.status_code == 503
    assert response.json()["detail"] == "OIDC_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_auth_config_reports_oidc_disabled(client: AsyncClient):
    response = await client.get("/api/v1/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["oidc_enabled"] is False
    assert payload["login_url"].endswith("/api/v1/auth/login")


@pytest.mark.asyncio
async def test_auth_config_reports_oidc_enabled(client: AsyncClient, monkeypatch):
    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router.settings, "zitadel_client_id", "local-dev-client")
    monkeypatch.setattr(
        auth_router.settings, "zitadel_client_secret", "local-dev-secret"
    )

    response = await client.get("/api/v1/auth/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["oidc_enabled"] is True
    assert payload["login_url"].endswith("/api/v1/auth/login")


@pytest.mark.asyncio
async def test_oidc_login_redirects_when_configured(client: AsyncClient, monkeypatch):
    from fastapi.responses import RedirectResponse

    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router.settings, "zitadel_client_id", "local-dev-client")
    monkeypatch.setattr(
        auth_router.settings, "zitadel_client_secret", "local-dev-secret"
    )
    _mock_zitadel_oauth(
        monkeypatch,
        auth_router,
        authorize_redirect=AsyncMock(
            return_value=RedirectResponse(
                url="http://localhost:8080/oauth/v2/authorize", status_code=302
            )
        ),
    )

    response = await client.get("/api/v1/auth/login", follow_redirects=False)
    assert response.status_code == 302
    assert "authorize" in response.headers["location"]


@pytest.mark.asyncio
async def test_oidc_callback_establishes_session(client: AsyncClient, monkeypatch):
    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router.settings, "zitadel_client_id", "local-dev-client")
    monkeypatch.setattr(
        auth_router.settings, "zitadel_client_secret", "local-dev-secret"
    )
    _mock_zitadel_oauth(
        monkeypatch,
        auth_router,
        authorize_access_token=AsyncMock(
            return_value={
                "userinfo": {
                    "sub": "oidc-user-1",
                    "email": "oidc@example.com",
                    "email_verified": True,
                    "name": "OIDC User",
                }
            }
        ),
    )

    response = await client.get(
        "/api/v1/auth/callback?code=abc", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == auth_router.settings.frontend_base_url

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "oidc@example.com"

    async with async_session_maker() as session:
        user = await session.scalar(
            select(User).where(User.zitadel_user_id == "oidc-user-1")
        )
        assert user is not None


@pytest.mark.asyncio
async def test_oidc_callback_redirects_on_missing_claims(
    client: AsyncClient, monkeypatch
):
    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router.settings, "zitadel_client_id", "local-dev-client")
    monkeypatch.setattr(
        auth_router.settings, "zitadel_client_secret", "local-dev-secret"
    )
    _mock_zitadel_oauth(
        monkeypatch,
        auth_router,
        authorize_access_token=AsyncMock(
            return_value={"userinfo": {"sub": "no-email"}}
        ),
    )

    response = await client.get(
        "/api/v1/auth/callback?code=abc", follow_redirects=False
    )
    assert response.status_code == 303
    assert "error=missing_claims" in response.headers["location"]
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_logout_redirects_to_frontend_when_oidc_disabled(client: AsyncClient):
    from app.config import get_settings

    response = await client.get("/api/v1/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == get_settings().frontend_base_url


@pytest.mark.asyncio
async def test_logout_redirects_through_zitadel_end_session(
    client: AsyncClient, monkeypatch
):
    import app.routers.auth as auth_router

    monkeypatch.setattr(auth_router.settings, "zitadel_client_id", "local-dev-client")
    monkeypatch.setattr(
        auth_router.settings, "zitadel_client_secret", "local-dev-secret"
    )
    monkeypatch.setattr(auth_router.settings, "zitadel_issuer", "http://localhost:8080")

    await login_user(client, "logout@example.com")
    response = await client.get("/api/v1/auth/logout", follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/oidc/v1/end_session" in location
    assert "client_id=local-dev-client" in location
    assert (await client.get("/api/v1/auth/me")).status_code == 401
