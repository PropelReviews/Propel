import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import auth_headers, create_tenant, login_user, register_user

from app.db.session import async_session_maker
from app.integrations.linear import oauth as linear_oauth
from app.models.connected_account import ConnectedAccount
from app.services import linear_connection as svc
from app.services import token_crypto


def _configure(monkeypatch) -> None:
    """Set a Fernet key + Linear OAuth credentials on the settings singleton."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(svc.settings, "token_encryption_key", key)
    monkeypatch.setattr(svc.settings, "oauth_linear_client_id", "client-id")
    monkeypatch.setattr(svc.settings, "oauth_linear_client_secret", "client-secret")
    token_crypto._fernet.cache_clear()


def _fake_token(access="access-1", refresh="refresh-1", expires_in=86399):
    return linear_oauth.LinearToken(
        access_token=access,
        refresh_token=refresh,
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        scopes=["read"],
    )


async def _user_id(client: AsyncClient, token: str) -> uuid.UUID:
    me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    return uuid.UUID(me.json()["id"])


def test_connect_state_roundtrip():
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    state = svc.build_connect_state(tenant_id, user_id)
    assert svc.verify_connect_state(state) == (tenant_id, user_id)


def test_connect_state_rejects_wrong_signature(monkeypatch):
    monkeypatch.setattr(svc.settings, "jwt_secret", "secret-a")
    state = svc.build_connect_state(uuid.uuid4(), uuid.uuid4())
    monkeypatch.setattr(svc.settings, "jwt_secret", "secret-b")
    with pytest.raises(Exception) as exc:
        svc.verify_connect_state(state)
    assert getattr(exc.value, "status_code", None) == 400


@pytest.mark.asyncio
async def test_authorize_requires_config(client: AsyncClient, monkeypatch):
    await register_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)

    monkeypatch.setattr(svc.settings, "oauth_linear_client_id", "")
    monkeypatch.setattr(svc.settings, "oauth_linear_client_secret", "")
    blocked = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections/linear/authorize",
        headers=auth_headers(token),
    )
    assert blocked.status_code == 503

    monkeypatch.setattr(svc.settings, "oauth_linear_client_id", "client-id")
    monkeypatch.setattr(svc.settings, "oauth_linear_client_secret", "client-secret")
    ok = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections/linear/authorize",
        headers=auth_headers(token),
    )
    assert ok.status_code == 200
    url = ok.json()["authorization_url"]
    assert url.startswith("https://linear.app/oauth/authorize")
    assert "actor=app" in url
    assert "scope=read" in url
    assert "prompt=consent" in url


@pytest.mark.asyncio
async def test_callback_creates_and_reconnects(client: AsyncClient, monkeypatch):
    _configure(monkeypatch)
    await register_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)
    user_id = await _user_id(client, token)
    tenant_id = uuid.UUID(tenant["id"])

    async def fake_exchange(code, redirect_uri):
        return _fake_token()

    async def fake_workspace(access_token):
        return "workspace-1", "Acme Workspace"

    monkeypatch.setattr(svc.linear_oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(svc.linear_oauth, "fetch_workspace", fake_workspace)

    state = svc.build_connect_state(tenant_id, user_id)
    resp = await client.get(
        f"/api/v1/connections/linear/callback?code=abc&state={state}",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "linear=connected" in resp.headers["location"]

    async with async_session_maker() as session:
        rows = (
            (
                await session.execute(
                    select(ConnectedAccount).where(
                        ConnectedAccount.tenant_id == tenant_id,
                        ConnectedAccount.provider == "linear",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        account = rows[0]
        assert account.auth_type == "oauth"
        assert account.external_account_id == "workspace-1"
        assert account.external_account_name == "Acme Workspace"
        assert account.scopes == ["read"]
        # Tokens are stored encrypted, but decrypt back to the originals.
        assert account.access_token_encrypted != "access-1"
        assert token_crypto.decrypt_token(account.access_token_encrypted) == "access-1"
        assert (
            token_crypto.decrypt_token(account.refresh_token_encrypted) == "refresh-1"
        )

    # Reconnecting the same workspace updates the existing row (no duplicate).
    state2 = svc.build_connect_state(tenant_id, user_id)
    resp2 = await client.get(
        f"/api/v1/connections/linear/callback?code=def&state={state2}",
        follow_redirects=False,
    )
    assert resp2.status_code == 303
    async with async_session_maker() as session:
        count = len(
            (
                await session.execute(
                    select(ConnectedAccount).where(
                        ConnectedAccount.tenant_id == tenant_id,
                        ConnectedAccount.provider == "linear",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert count == 1


@pytest.mark.asyncio
async def test_callback_rejects_bad_state(client: AsyncClient, monkeypatch):
    _configure(monkeypatch)
    resp = await client.get(
        "/api/v1/connections/linear/callback?code=abc&state=not-valid",
        follow_redirects=False,
    )
    # Failures bounce back to the SPA with an error marker, never a 500.
    assert resp.status_code == 303
    assert "linear=error" in resp.headers["location"]


@pytest.mark.asyncio
async def test_get_access_token_refreshes_when_expiring(monkeypatch):
    _configure(monkeypatch)
    account = ConnectedAccount(
        tenant_id=uuid.uuid4(),
        provider="linear",
        auth_type="oauth",
        external_account_id="workspace-1",
        external_account_name="Acme",
        access_token_encrypted=token_crypto.encrypt_token("old-access"),
        refresh_token_encrypted=token_crypto.encrypt_token("old-refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        scopes=["read"],
    )

    async def fake_refresh(refresh_token):
        assert refresh_token == "old-refresh"
        return _fake_token(access="new-access", refresh="new-refresh")

    monkeypatch.setattr(svc.linear_oauth, "refresh_access_token", fake_refresh)

    class _FakeSession:
        async def commit(self):
            return None

        async def refresh(self, _obj):
            return None

    token = await svc.get_access_token(_FakeSession(), account)
    assert token == "new-access"
    assert token_crypto.decrypt_token(account.access_token_encrypted) == "new-access"
    assert token_crypto.decrypt_token(account.refresh_token_encrypted) == "new-refresh"


@pytest.mark.asyncio
async def test_get_access_token_returns_stored_when_fresh(monkeypatch):
    _configure(monkeypatch)
    account = ConnectedAccount(
        tenant_id=uuid.uuid4(),
        provider="linear",
        auth_type="oauth",
        external_account_id="workspace-1",
        access_token_encrypted=token_crypto.encrypt_token("fresh-access"),
        refresh_token_encrypted=token_crypto.encrypt_token("fresh-refresh"),
        token_expires_at=datetime.now(UTC) + timedelta(hours=12),
        scopes=["read"],
    )

    async def fail_refresh(refresh_token):  # pragma: no cover - must not be called
        raise AssertionError("should not refresh a fresh token")

    monkeypatch.setattr(svc.linear_oauth, "refresh_access_token", fail_refresh)

    class _FakeSession:
        async def commit(self):
            return None

        async def refresh(self, _obj):
            return None

    token = await svc.get_access_token(_FakeSession(), account)
    assert token == "fresh-access"
