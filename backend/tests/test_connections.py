import hashlib
import hmac
import json
import uuid

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from tests.conftest import act_as_headers, create_tenant, login_test_user, login_user

from app.db.session import async_session_maker
from app.models.connected_account import ConnectedAccount
from app.models.tenant import Tenant
from app.services import connections as connection_service


async def _seed_connection(
    tenant_id: uuid.UUID, installation_id: str = "12345", status: str = "active"
) -> uuid.UUID:
    async with async_session_maker() as session:
        account = ConnectedAccount(
            tenant_id=tenant_id,
            provider="github",
            auth_type="github_app_installation",
            external_account_id=installation_id,
            external_account_name="acme",
            status=status,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return account.id


def test_install_state_roundtrip():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    state = connection_service.build_install_state(tenant_id, user_id)

    got_tenant, got_user = connection_service.verify_install_state(state)
    assert got_tenant == tenant_id
    assert got_user == user_id


def test_install_state_rejects_garbage():
    with pytest.raises(HTTPException) as exc:
        connection_service.verify_install_state("!!!not-valid!!!")
    assert exc.value.status_code == 400


def test_install_state_rejects_wrong_signature(monkeypatch):
    monkeypatch.setattr(connection_service.settings, "session_secret", "secret-a")
    state = connection_service.build_install_state(uuid.uuid4(), uuid.uuid4())
    # A state signed under a different secret must not verify.
    monkeypatch.setattr(connection_service.settings, "session_secret", "secret-b")
    with pytest.raises(HTTPException) as exc:
        connection_service.verify_install_state(state)
    assert exc.value.status_code == 400


def test_webhook_signature_requires_secret_and_matches(monkeypatch):
    monkeypatch.setattr(
        connection_service.settings, "github_app_webhook_secret", "whsec"
    )
    body = b'{"action":"created"}'
    good = "sha256=" + hmac.new(b"whsec", body, hashlib.sha256).hexdigest()

    assert connection_service.verify_webhook_signature(body, good) is True
    assert connection_service.verify_webhook_signature(body, "sha256=bad") is False
    assert connection_service.verify_webhook_signature(body, None) is False


@pytest.mark.asyncio
async def test_install_url_requires_slug(client: AsyncClient, monkeypatch):
    await login_test_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)

    monkeypatch.setattr(connection_service.settings, "github_app_slug", "")
    blocked = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections/github/install",
        headers=act_as_headers(token),
    )
    assert blocked.status_code == 503

    monkeypatch.setattr(connection_service.settings, "github_app_slug", "propel-app")
    ok = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections/github/install",
        headers=act_as_headers(token),
    )
    assert ok.status_code == 200
    assert "github.com/apps/propel-app/installations/new" in ok.json()["install_url"]


@pytest.mark.asyncio
async def test_list_and_pause_connection(client: AsyncClient):
    await login_test_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)
    connection_id = await _seed_connection(uuid.UUID(tenant["id"]))

    listed = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections",
        headers=act_as_headers(token),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["external_account_id"] == "12345"

    paused = await client.patch(
        f"/api/v1/tenants/{tenant['id']}/connections/{connection_id}",
        json={"status": "paused"},
        headers=act_as_headers(token),
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"


@pytest.mark.asyncio
async def test_non_admin_cannot_list_connections(client: AsyncClient):
    await login_test_user(client, "admin@example.com")
    admin_token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, admin_token)

    await login_test_user(client, "member@example.com")
    member_token = await login_user(client, "member@example.com")
    invite = await client.post(
        f"/api/v1/tenants/{tenant['id']}/invites",
        json={"email": "member@example.com", "role": "member"},
        headers=act_as_headers(admin_token),
    )
    accept_token = invite.json()["invite_url"].split("/")[-2]
    await client.post(
        f"/api/v1/invites/{accept_token}/accept",
        headers=act_as_headers(member_token),
    )

    forbidden = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections",
        headers=act_as_headers(member_token),
    )
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_webhook_revokes_connection(client: AsyncClient, monkeypatch):
    await login_test_user(client, "admin@example.com")
    token = await login_user(client, "admin@example.com")
    tenant = await create_tenant(client, token)
    await _seed_connection(uuid.UUID(tenant["id"]), installation_id="99")

    monkeypatch.setattr(
        connection_service.settings, "github_app_webhook_secret", "whsec"
    )
    payload = {"action": "deleted", "installation": {"id": 99}}
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"whsec", body, hashlib.sha256).hexdigest()

    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "installation",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202

    listed = await client.get(
        f"/api/v1/tenants/{tenant['id']}/connections",
        headers=act_as_headers(token),
    )
    assert listed.json()[0]["status"] == "revoked"


@pytest.mark.asyncio
async def test_webhook_bad_signature_rejected(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        connection_service.settings, "github_app_webhook_secret", "whsec"
    )
    response = await client.post(
        "/api/v1/webhooks/github",
        content=b'{"action":"deleted","installation":{"id":1}}',
        headers={
            "X-Hub-Signature-256": "sha256=deadbeef",
            "X-GitHub-Event": "installation",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Installation discovery
# --------------------------------------------------------------------------- #
def _installation_payload(
    installation_id: int, login: str, suspended: bool = False
) -> dict:
    return {
        "id": installation_id,
        "account": {"login": login},
        "permissions": {"members": "read"},
        "suspended_at": "2026-01-01T00:00:00Z" if suspended else None,
    }


def _mock_installations(monkeypatch, installations: list[dict]) -> None:
    async def fake_list() -> list[dict]:
        return installations

    monkeypatch.setattr(connection_service.app_auth, "list_installations", fake_list)


async def _get_account(installation_id: str) -> ConnectedAccount:
    async with async_session_maker() as session:
        return (
            await session.execute(
                select(ConnectedAccount).where(
                    ConnectedAccount.external_account_id == installation_id
                )
            )
        ).scalar_one()


@pytest.fixture(autouse=True)
def roster_imports(monkeypatch):
    """Roster import hits GitHub live; stub it out and record the orgs imported."""
    imported: list[str] = []

    async def fake_import(session, account):
        imported.append(account.external_account_name)
        return 0

    monkeypatch.setattr(
        connection_service.github_identity, "import_roster_for_account", fake_import
    )
    return imported


@pytest.mark.asyncio
async def test_sync_installations_auto_provisions_tenant(
    clean_db, monkeypatch, roster_imports
):
    _mock_installations(monkeypatch, [_installation_payload(555, "AcmeOrg")])

    async with async_session_maker() as session:
        summary = await connection_service.sync_installations_from_github(session)
    assert summary == {"created": 1, "updated": 0, "revoked": 0}
    # A fresh org install triggers an immediate member-roster import.
    assert roster_imports == ["AcmeOrg"]

    account = await _get_account("555")
    assert account.status == "active"
    assert account.external_account_name == "AcmeOrg"
    async with async_session_maker() as session:
        tenant = await session.get(Tenant, account.tenant_id)
    assert tenant.slug == "acmeorg"
    assert tenant.name == "AcmeOrg"

    # Re-running is a no-op.
    async with async_session_maker() as session:
        summary = await connection_service.sync_installations_from_github(session)
    assert summary == {"created": 0, "updated": 0, "revoked": 0}


@pytest.mark.asyncio
async def test_sync_installations_reuses_tenant_by_slug(clean_db, monkeypatch):
    async with async_session_maker() as session:
        tenant = Tenant(name="Acme", slug="acmeorg")
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    _mock_installations(monkeypatch, [_installation_payload(556, "AcmeOrg")])
    async with async_session_maker() as session:
        await connection_service.sync_installations_from_github(session)

    account = await _get_account("556")
    assert account.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_sync_installations_pauses_and_revokes(clean_db, monkeypatch):
    _mock_installations(
        monkeypatch,
        [_installation_payload(1, "OrgOne"), _installation_payload(2, "OrgTwo")],
    )
    async with async_session_maker() as session:
        await connection_service.sync_installations_from_github(session)

    # OrgOne is now suspended; OrgTwo uninstalled the app entirely.
    _mock_installations(
        monkeypatch, [_installation_payload(1, "OrgOne", suspended=True)]
    )
    async with async_session_maker() as session:
        summary = await connection_service.sync_installations_from_github(session)
    assert summary == {"created": 0, "updated": 1, "revoked": 1}

    assert (await _get_account("1")).status == "paused"
    assert (await _get_account("2")).status == "revoked"


@pytest.mark.asyncio
async def test_webhook_created_auto_provisions(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(
        connection_service.settings, "github_app_webhook_secret", "whsec"
    )
    payload = {
        "action": "created",
        "installation": _installation_payload(777, "NewOrg"),
    }
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"whsec", body, hashlib.sha256).hexdigest()

    response = await client.post(
        "/api/v1/webhooks/github",
        content=body,
        headers={
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "installation",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 202

    account = await _get_account("777")
    assert account.status == "active"
    assert account.external_account_name == "NewOrg"
    async with async_session_maker() as session:
        tenant = await session.get(Tenant, account.tenant_id)
    assert tenant.slug == "neworg"
