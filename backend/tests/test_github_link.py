"""Self-service "Connect with GitHub" account linking."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import auth_headers, login_user, register_user

from app.auth.oauth import github_oauth_client
from app.db.session import async_session_maker
from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    AuthType,
    GitHubOrgRole,
    IdentityLinkMethod,
    IdentityStatus,
    IntegrationProvider,
)
from app.models.external_identity import ExternalIdentity
from app.models.membership import TenantMembership
from app.models.tenant import Tenant
from app.models.user import OAuthAccount, User
from app.services import github_link

_GITHUB = IntegrationProvider.github.value


def _mock_github_oauth(monkeypatch, *, account_id: str, email: str | None) -> None:
    async def fake_access_token(code, redirect_uri, code_verifier=None):
        return {"access_token": f"tok-{code}"}

    async def fake_id_email(token):
        return account_id, email

    monkeypatch.setattr(github_oauth_client, "get_access_token", fake_access_token)
    monkeypatch.setattr(github_oauth_client, "get_id_email", fake_id_email)


# --------------------------------------------------------------------------- #
# Signed state
# --------------------------------------------------------------------------- #
def test_link_state_round_trips():
    user_id = uuid.uuid4()
    state = github_link.build_link_state(user_id)
    assert github_link.verify_link_state(state) == user_id


def test_link_state_rejects_tampering():
    import base64

    state = github_link.build_link_state(uuid.uuid4())
    raw = base64.urlsafe_b64decode(state.encode()).decode()
    payload, _signature = raw.rsplit(":", 1)
    forged = base64.urlsafe_b64encode(f"{payload}:{'0' * 64}".encode()).decode()
    with pytest.raises(Exception):
        github_link.verify_link_state(forged)


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_authorize_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/github/link/authorize")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_returns_url_when_configured(
    client: AsyncClient, monkeypatch
):
    await register_user(client, "linker@example.com")
    token = await login_user(client, "linker@example.com")

    monkeypatch.setattr(github_link.settings, "oauth_github_client_id", "cid")
    monkeypatch.setattr(github_link.settings, "oauth_github_client_secret", "secret")

    async def fake_authorize_url(redirect_uri, state=None, **kwargs):
        return f"https://github.com/login/oauth/authorize?state={state}"

    monkeypatch.setattr(
        github_oauth_client, "get_authorization_url", fake_authorize_url
    )

    response = await client.get(
        "/api/v1/auth/github/link/authorize", headers=auth_headers(token)
    )
    assert response.status_code == 200
    assert "github.com/login/oauth/authorize" in response.json()["authorization_url"]


@pytest.mark.asyncio
async def test_authorize_503_when_github_not_configured(client: AsyncClient):
    await register_user(client, "noconfig@example.com")
    token = await login_user(client, "noconfig@example.com")
    response = await client.get(
        "/api/v1/auth/github/link/authorize", headers=auth_headers(token)
    )
    assert response.status_code == 503


# --------------------------------------------------------------------------- #
# Completing the link
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_complete_link_creates_oauth_account_and_claims_org_identity(
    clean_db, monkeypatch
):
    _mock_github_oauth(monkeypatch, account_id="555", email="me@personal.com")

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
        # The user registered with a different (work) email; their GitHub email
        # is private, so org sync parked them as pending_email.
        user = User(
            email="dev@propel.ninja",
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            ExternalIdentity(
                tenant_id=tenant.id,
                connected_account_id=account.id,
                provider=_GITHUB,
                external_user_id="555",
                external_login="sarossilli",
                status=IdentityStatus.pending_email.value,
                github_org_role=GitHubOrgRole.member.value,
            )
        )
        await session.commit()
        user_id = user.id
        tenant_id = tenant.id

        state = github_link.build_link_state(user_id)
        await github_link.complete_link(session, code="abc", state=state)

    async with async_session_maker() as session:
        oauth = await session.scalar(
            select(OAuthAccount).where(OAuthAccount.user_id == user_id)
        )
        assert oauth is not None
        assert oauth.oauth_name == _GITHUB
        assert oauth.account_id == "555"

        identity = await session.scalar(
            select(ExternalIdentity).where(ExternalIdentity.external_login == "sarossilli")
        )
        assert identity.propel_user_id == user_id
        assert identity.status == IdentityStatus.linked.value
        assert identity.link_method == IdentityLinkMethod.oauth_id.value

        membership = await session.scalar(
            select(TenantMembership).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
            )
        )
        assert membership is not None


@pytest.mark.asyncio
async def test_complete_link_is_idempotent(clean_db, monkeypatch):
    _mock_github_oauth(monkeypatch, account_id="777", email="x@y.com")

    async with async_session_maker() as session:
        user = User(
            email="repeat@propel.ninja",
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        user_id = user.id

        state = github_link.build_link_state(user_id)
        await github_link.complete_link(session, code="a", state=state)
        await github_link.complete_link(session, code="b", state=state)

    async with async_session_maker() as session:
        rows = (
            (await session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user_id)))
            .scalars()
            .all()
        )
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_complete_link_conflict_when_github_owned_by_other_user(
    clean_db, monkeypatch
):
    _mock_github_oauth(monkeypatch, account_id="888", email="shared@x.com")

    async with async_session_maker() as session:
        other = User(
            email="other@propel.ninja",
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        session.add(other)
        await session.flush()
        session.add(
            OAuthAccount(
                user_id=other.id,
                oauth_name=_GITHUB,
                access_token="t",
                account_id="888",
                account_email="shared@x.com",
            )
        )
        me = User(
            email="me@propel.ninja",
            hashed_password="x",
            is_active=True,
            is_verified=True,
        )
        session.add(me)
        await session.commit()
        me_id = me.id

        state = github_link.build_link_state(me_id)
        with pytest.raises(Exception) as exc:
            await github_link.complete_link(session, code="c", state=state)
        assert getattr(exc.value, "status_code", None) == 409


@pytest.mark.asyncio
async def test_me_reports_github_connection(client: AsyncClient):
    await register_user(client, "connected@example.com")
    token = await login_user(client, "connected@example.com")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.json()["github"]["connected"] is False

    user_id = uuid.UUID(me.json()["id"])
    async with async_session_maker() as session:
        session.add(
            OAuthAccount(
                user_id=user_id,
                oauth_name=_GITHUB,
                access_token="t",
                account_id="999",
                account_email="gh@example.com",
            )
        )
        await session.commit()

    me2 = await client.get("/api/v1/auth/me", headers=auth_headers(token))
    github = me2.json()["github"]
    assert github["connected"] is True
    assert github["account_id"] == "999"
    assert github["account_email"] == "gh@example.com"
