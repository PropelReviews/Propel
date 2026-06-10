"""Orchestrator builds the right tap-github discovery-mode env per job."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.session import async_session_maker
from app.ingestion import orchestrator
from app.integrations.github import app_auth
from app.models.connected_account import ConnectedAccount
from app.models.enums import AuthType, IngestionRunStatus, IntegrationProvider
from app.models.ingestion_run import IngestionRun
from app.models.raw_record import RawRecord
from app.models.tenant import Tenant

_ORG = "acme"


@pytest.fixture(autouse=True)
def _fake_installation_token(monkeypatch):
    async def _token(_installation_id):
        return app_auth.InstallationToken(token="tok", expires_at=datetime.now(UTC))

    monkeypatch.setattr(app_auth, "get_installation_token", _token)


def _job(name):
    return next(j for j in orchestrator.JOBS if j.name == name)


async def _seed(session) -> ConnectedAccount:
    tenant = Tenant(name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    account = ConnectedAccount(
        tenant_id=tenant.id,
        provider=IntegrationProvider.github.value,
        auth_type=AuthType.github_app_installation.value,
        external_account_id="42",
        external_account_name=_ORG,
    )
    session.add(account)
    await session.flush()
    return account


async def _run_for(session, account, job) -> IngestionRun:
    run = IngestionRun(
        tenant_id=account.tenant_id,
        connected_account_id=account.id,
        source=IntegrationProvider.github.value,
        resource_type=job.resource_type,
        status=IngestionRunStatus.running.value,
    )
    session.add(run)
    await session.flush()
    return run


@pytest.mark.asyncio
async def test_org_job_sets_organizations_array(clean_db):
    async with async_session_maker() as session:
        account = await _seed(session)
        job = _job("github_org_sync")
        run = await _run_for(session, account, job)

        env = await orchestrator._build_env(session, account, job, run)

    assert env["TAP_GITHUB_ORGANIZATIONS"] == json.dumps([_ORG])
    assert "TAP_GITHUB_REPOSITORIES" not in env
    assert "TAP_GITHUB_START_DATE" in env


@pytest.mark.asyncio
async def test_profiles_job_targets_synced_member_logins(clean_db):
    async with async_session_maker() as session:
        account = await _seed(session)
        for login, gid in (("octocat", 1), ("dev", 2)):
            session.add(
                RawRecord(
                    tenant_id=account.tenant_id,
                    source="github",
                    resource_type="organization_members",
                    source_id=str(gid),
                    payload={"login": login, "id": gid},
                )
            )
        await session.flush()

        job = _job("github_user_profiles_sync")
        run = await _run_for(session, account, job)
        env = await orchestrator._build_env(session, account, job, run)

    assert set(json.loads(env["TAP_GITHUB_USER_USERNAMES"])) == {"octocat", "dev"}
    assert "TAP_GITHUB_ORGANIZATIONS" not in env


@pytest.mark.asyncio
async def test_profiles_job_skips_when_no_members(clean_db):
    async with async_session_maker() as session:
        account = await _seed(session)
        job = _job("github_user_profiles_sync")
        run = await _run_for(session, account, job)

        env = await orchestrator._build_env(session, account, job, run)

    assert env is None


def _patch_copilot_probe(monkeypatch, available: bool):
    calls: list[tuple[str, str]] = []

    async def _probe(token, org):
        calls.append((token, org))
        return available

    monkeypatch.setattr(orchestrator.copilot, "copilot_metrics_available", _probe)
    return calls


@pytest.mark.asyncio
async def test_copilot_job_skips_when_org_has_no_copilot(clean_db, monkeypatch):
    calls = _patch_copilot_probe(monkeypatch, available=False)
    async with async_session_maker() as session:
        account = await _seed(session)
        job = _job("copilot_sync")
        run = await _run_for(session, account, job)

        env = await orchestrator._build_env(session, account, job, run)

        assert env is None
        assert calls == [("tok", _ORG)]
        # The probe result is cached on the account metadata.
        await session.refresh(account)
        cached = account.meta["copilot_metrics"]
        assert cached["available"] is False
        assert cached["checked_at"]


@pytest.mark.asyncio
async def test_copilot_job_runs_when_org_has_copilot(clean_db, monkeypatch):
    _patch_copilot_probe(monkeypatch, available=True)
    async with async_session_maker() as session:
        account = await _seed(session)
        job = _job("copilot_sync")
        run = await _run_for(session, account, job)

        env = await orchestrator._build_env(session, account, job, run)

        assert env["COPILOT_ORG"] == _ORG
        await session.refresh(account)
        assert account.meta["copilot_metrics"]["available"] is True


@pytest.mark.asyncio
async def test_copilot_fresh_cache_skips_probe(clean_db, monkeypatch):
    calls = _patch_copilot_probe(monkeypatch, available=True)
    async with async_session_maker() as session:
        account = await _seed(session)
        account.meta = {
            "copilot_metrics": {
                "available": False,
                "checked_at": datetime.now(UTC).isoformat(),
            }
        }
        job = _job("copilot_sync")
        run = await _run_for(session, account, job)

        env = await orchestrator._build_env(session, account, job, run)

    assert env is None
    assert calls == []


@pytest.mark.asyncio
async def test_copilot_stale_cache_reprobes(clean_db, monkeypatch):
    calls = _patch_copilot_probe(monkeypatch, available=True)
    async with async_session_maker() as session:
        account = await _seed(session)
        account.meta = {
            "copilot_metrics": {
                "available": False,
                "checked_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
            }
        }
        job = _job("copilot_sync")
        run = await _run_for(session, account, job)

        env = await orchestrator._build_env(session, account, job, run)

        assert env["COPILOT_ORG"] == _ORG
        assert calls == [("tok", _ORG)]
        await session.refresh(account)
        assert account.meta["copilot_metrics"]["available"] is True
