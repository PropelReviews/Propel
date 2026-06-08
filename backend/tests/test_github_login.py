"""Sign in / sign up with GitHub (redirect-based OAuth login)."""

import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import auth_headers, register_user

from app.db.session import async_session_maker
from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    AuthType,
    GitHubOrgRole,
    IdentityStatus,
    IntegrationProvider,
)
from app.models.external_identity import ExternalIdentity
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import OAuthAccount, User
from app.services import github_login

_GITHUB = IntegrationProvider.github.value


def _mock_exchange(monkeypatch, *, account_id: str, email: str | None) -> None:
    async def fake_exchange(code):
        return f"tok-{code}", account_id, email

    monkeypatch.setattr(github_login, "exchange_code", fake_exchange)


# --------------------------------------------------------------------------- #
# Signed state
# --------------------------------------------------------------------------- #
def test_login_state_round_trips():
    state = github_login.build_login_state()
    github_login.verify_login_state(state)  # does not raise


def test_login_state_rejects_tampering():
    import base64

    state = github_login.build_login_state()
    raw = base64.urlsafe_b64decode(state.encode()).decode()
    payload, _sig = raw.rsplit(":", 1)
    forged = base64.urlsafe_b64encode(f"{payload}:{'0' * 64}".encode()).decode()
    with pytest.raises(HTTPException):
        github_login.verify_login_state(forged)


# --------------------------------------------------------------------------- #
# Authorize
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_authorize_requires_no_auth_but_needs_config(client: AsyncClient):
    # Not configured in the test env → 503 (and crucially, no auth header needed).
    response = await client.get("/api/v1/auth/github/login/authorize")
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_authorize_returns_url_when_configured(client: AsyncClient, monkeypatch):
    from app.auth.oauth import github_oauth_client

    monkeypatch.setattr(github_login.settings, "oauth_github_client_id", "cid")
    monkeypatch.setattr(github_login.settings, "oauth_github_client_secret", "secret")

    async def fake_authorize_url(redirect_uri, state=None, **kwargs):
        return f"https://github.com/login/oauth/authorize?state={state}"

    monkeypatch.setattr(
        github_oauth_client, "get_authorization_url", fake_authorize_url
    )

    response = await client.get("/api/v1/auth/github/login/authorize")
    assert response.status_code == 200
    assert "github.com/login/oauth/authorize" in response.json()["authorization_url"]


# --------------------------------------------------------------------------- #
# Callback
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_callback_signs_up_new_user_and_issues_token(
    client: AsyncClient, monkeypatch
):
    _mock_exchange(monkeypatch, account_id="2001", email="newgh@example.com")
    state = github_login.build_login_state()

    response = await client.get(
        f"/api/v1/auth/github/login/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    # Redirect must target the SPA origin (separate from the API), not the
    # OAuth callback host.
    assert location.startswith(
        f"{github_login.settings.frontend_base_url}/auth/github/callback#access_token="
    )

    token = location.split("#access_token=")[1]
    # The minted token authenticates as the new user.
    me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "newgh@example.com"
    assert me.json()["github"]["connected"] is True


@pytest.mark.asyncio
async def test_callback_logs_in_existing_github_user(client: AsyncClient, monkeypatch):
    await register_user(client, "existing@example.com")
    async with async_session_maker() as session:
        user = await session.scalar(
            select(User).where(User.email == "existing@example.com")
        )
        session.add(
            OAuthAccount(
                user_id=user.id,
                oauth_name=_GITHUB,
                access_token="old",
                account_id="3001",
                account_email="existing@example.com",
            )
        )
        await session.commit()
        user_id = user.id

    _mock_exchange(monkeypatch, account_id="3001", email="existing@example.com")
    state = github_login.build_login_state()
    response = await client.get(
        f"/api/v1/auth/github/login/callback?code=xyz&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 303
    token = response.headers["location"].split("#access_token=")[1]
    me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.json()["id"] == str(user_id)


@pytest.mark.asyncio
async def test_callback_links_pending_org_identity_on_login(
    client: AsyncClient, monkeypatch
):
    async with async_session_maker() as session:
        tenant = Tenant(name="Propel", slug=f"propel-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        await session.flush()
        account = ConnectedAccount(
            tenant_id=tenant.id,
            provider=_GITHUB,
            auth_type=AuthType.github_app_installation.value,
            external_account_id="1",
            external_account_name="propel",
        )
        session.add(account)
        await session.flush()
        session.add(
            ExternalIdentity(
                tenant_id=tenant.id,
                connected_account_id=account.id,
                provider=_GITHUB,
                external_user_id="4001",
                external_login="newbie",
                status=IdentityStatus.pending_email.value,
                github_org_role=GitHubOrgRole.member.value,
            )
        )
        await session.commit()
        tenant_id = tenant.id

    _mock_exchange(monkeypatch, account_id="4001", email="newbie@example.com")
    state = github_login.build_login_state()
    response = await client.get(
        f"/api/v1/auth/github/login/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert response.status_code == 303

    async with async_session_maker() as session:
        user = await session.scalar(
            select(User).where(User.email == "newbie@example.com")
        )
        assert user is not None
        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "newbie")
        )
        assert identity.propel_user_id == user.id
        assert identity.status == IdentityStatus.linked.value
        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user.id,
            )
        )
        assert membership is not None


@pytest.mark.asyncio
async def test_callback_bad_state_redirects_with_error(
    client: AsyncClient, monkeypatch
):
    _mock_exchange(monkeypatch, account_id="5001", email="x@example.com")
    response = await client.get(
        "/api/v1/auth/github/login/callback?code=abc&state=not-a-valid-state",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "#error=" in response.headers["location"]
