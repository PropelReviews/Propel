import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.db.session import async_session_maker
from app.ingestion import meltano_runner, orchestrator
from app.integrations.github import app_auth
from app.models.connected_account import ConnectedAccount
from app.models.ingestion_run import IngestionRun
from app.models.tenant import Tenant

GITHUB_JOB = next(j for j in orchestrator.JOBS if j.name == "github_commits_sync")


async def _seed_account(status: str = "active") -> ConnectedAccount:
    async with async_session_maker() as session:
        slug = uuid.uuid4().hex[:12]
        tenant = Tenant(name=f"tenant-{slug}", slug=slug)
        session.add(tenant)
        await session.flush()
        account = ConnectedAccount(
            tenant_id=tenant.id,
            provider="github",
            auth_type="github_app_installation",
            external_account_id="42",
            external_account_name="acme",
            status=status,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        session.expunge(account)
        return account


def _patch_github(monkeypatch, *, repos=("acme/web",)):
    async def fake_token(installation_id):
        return app_auth.InstallationToken(
            token="ghs_test", expires_at=datetime.now(UTC)
        )

    async def fake_repos(token):
        return list(repos)

    monkeypatch.setattr(orchestrator.app_auth, "get_installation_token", fake_token)
    monkeypatch.setattr(
        orchestrator.app_auth, "list_installation_repositories", fake_repos
    )


@pytest.mark.asyncio
async def test_successful_run_records_lifecycle(client, monkeypatch):
    # `client` applies migrations + a clean DB.
    account = await _seed_account()
    _patch_github(monkeypatch)

    captured_env: dict[str, str] = {}

    async def fake_run(job, env, **kwargs):
        captured_env.update(env)
        return meltano_runner.RunResult(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fake_run)

    async with async_session_maker() as session:
        run = await orchestrator.run_account_job(session, account, GITHUB_JOB)

    assert run is not None
    assert run.status == "success"
    assert run.finished_at is not None
    assert run.resource_type == "github.commits"
    # No real Meltano wrote rows, so counts are zero but populated.
    assert run.records_pulled == 0
    assert run.datapoints_written == 0
    assert run.cursor and "watermark" in run.cursor

    assert captured_env["PROPEL_TENANT_ID"] == str(account.tenant_id)
    assert captured_env["PROPEL_RUN_ID"] == str(run.id)
    assert captured_env["TAP_GITHUB_REPOSITORIES"] == '["acme/web"]'
    assert "TAP_GITHUB_START_DATE" in captured_env


@pytest.mark.asyncio
async def test_failed_run_is_marked_error(client, monkeypatch):
    account = await _seed_account()
    _patch_github(monkeypatch)

    async def fake_run(job, env, **kwargs):
        return meltano_runner.RunResult(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fake_run)

    async with async_session_maker() as session:
        run = await orchestrator.run_account_job(session, account, GITHUB_JOB)

    assert run is not None
    assert run.status == "error"
    assert run.error is not None and "boom" in run.error


@pytest.mark.asyncio
async def test_overlap_guard_skips_when_run_in_progress(client, monkeypatch):
    account = await _seed_account()
    _patch_github(monkeypatch)

    async with async_session_maker() as session:
        session.add(
            IngestionRun(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                source="github",
                resource_type="github.commits",
                status="running",
            )
        )
        await session.commit()

    async def fail_run(job, env, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("Meltano should not run while a run is in progress")

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fail_run)

    async with async_session_maker() as session:
        result = await orchestrator.run_account_job(session, account, GITHUB_JOB)
        assert result is None
        total = await session.scalar(
            select(func.count())
            .select_from(IngestionRun)
            .where(IngestionRun.connected_account_id == account.id)
        )
        assert total == 1


@pytest.mark.asyncio
async def test_clear_stale_runs_marks_old_running_as_error(client):
    account = await _seed_account()
    now = datetime.now(UTC)

    async with async_session_maker() as session:
        stale = IngestionRun(
            tenant_id=account.tenant_id,
            connected_account_id=account.id,
            source="github",
            resource_type="github",
            status="running",
            started_at=now - timedelta(hours=3),
        )
        fresh = IngestionRun(
            tenant_id=account.tenant_id,
            connected_account_id=account.id,
            source="github",
            resource_type="github.org_members",
            status="running",
            started_at=now - timedelta(minutes=5),
        )
        session.add_all([stale, fresh])
        await session.commit()
        stale_id, fresh_id = stale.id, fresh.id

    async with async_session_maker() as session:
        cleared = await orchestrator._clear_stale_runs(session)
    assert cleared == 1

    async with async_session_maker() as session:
        stale_row = await session.get(IngestionRun, stale_id)
        fresh_row = await session.get(IngestionRun, fresh_id)
    assert stale_row.status == "error"
    assert stale_row.finished_at is not None
    assert stale_row.error and "stale run cleanup" in stale_row.error
    # A recently started run is left alone (it may still be making progress).
    assert fresh_row.status == "running"


@pytest.mark.asyncio
async def test_run_all_reaps_stale_run_so_next_run_proceeds(client, monkeypatch):
    account = await _seed_account()
    _patch_github(monkeypatch)

    # A run stuck `running` from a killed worker would block the overlap guard.
    async with async_session_maker() as session:
        session.add(
            IngestionRun(
                tenant_id=account.tenant_id,
                connected_account_id=account.id,
                source="github",
                resource_type="github.commits",
                status="running",
                started_at=datetime.now(UTC) - timedelta(hours=3),
            )
        )
        await session.commit()

    ran_jobs: list[str] = []

    async def fake_run(job, env, **kwargs):
        ran_jobs.append(job)
        return meltano_runner.RunResult(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fake_run)

    await orchestrator.run_all(job_name="github_commits_sync")

    # The stale run was reaped at batch start, so the commits job actually ran.
    assert ran_jobs == ["github_commits_sync"]

    async with async_session_maker() as session:
        statuses = (
            (
                await session.execute(
                    select(IngestionRun.status).where(
                        IngestionRun.connected_account_id == account.id,
                        IngestionRun.resource_type == "github.commits",
                    )
                )
            )
            .scalars()
            .all()
        )
    assert "error" in statuses  # the reaped stale run
    assert "success" in statuses  # the fresh run that proceeded


@pytest.mark.asyncio
async def test_run_all_skips_paused_accounts(client, monkeypatch):
    await _seed_account(status="paused")
    _patch_github(monkeypatch)

    async def fail_run(job, env, **kwargs):  # pragma: no cover - must not run
        raise AssertionError("Paused accounts must not be ingested")

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fail_run)

    await orchestrator.run_all()

    async with async_session_maker() as session:
        total = await session.scalar(select(func.count()).select_from(IngestionRun))
        assert total == 0


@pytest.mark.asyncio
async def test_github_auth_failure_pauses_connection(client, monkeypatch):
    account = await _seed_account()

    async def fail_token(installation_id):
        raise app_auth.GitHubAppAuthError(
            "Installation token exchange failed (401): bad credentials"
        )

    monkeypatch.setattr(orchestrator.app_auth, "get_installation_token", fail_token)

    async with async_session_maker() as session:
        # Re-load so the orchestrator writes onto a session-bound instance.
        db_account = await session.get(ConnectedAccount, account.id)
        run = await orchestrator.run_account_job(session, db_account, GITHUB_JOB)

    assert run is not None
    assert run.status == "error"

    async with async_session_maker() as session:
        updated = await session.get(ConnectedAccount, account.id)
        assert updated.status == "paused"
        assert updated.meta["auth"]["reason"] == "GitHubAppAuthError"
        assert "Authentication failed" in updated.meta["auth"]["message"] or (
            "authentication failed" in updated.meta["auth"]["message"].lower()
        )


@pytest.mark.asyncio
async def test_github_404_auth_failure_revokes_connection(client, monkeypatch):
    account = await _seed_account()

    async def fail_token(installation_id):
        raise app_auth.GitHubAppAuthError(
            "Installation token exchange failed (404): Not Found"
        )

    monkeypatch.setattr(orchestrator.app_auth, "get_installation_token", fail_token)

    async with async_session_maker() as session:
        db_account = await session.get(ConnectedAccount, account.id)
        await orchestrator.run_account_job(session, db_account, GITHUB_JOB)

    async with async_session_maker() as session:
        updated = await session.get(ConnectedAccount, account.id)
        assert updated.status == "revoked"
        assert "missing or inaccessible" in updated.meta["auth"]["message"]


@pytest.mark.asyncio
async def test_meltano_auth_like_failure_pauses_connection(client, monkeypatch):
    account = await _seed_account()
    _patch_github(monkeypatch)

    async def fake_run(job, env, **kwargs):
        return meltano_runner.RunResult(
            returncode=1,
            stdout="",
            stderr="HTTP Error 401: Unauthorized — bad credentials from GitHub",
        )

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fake_run)

    async with async_session_maker() as session:
        db_account = await session.get(ConnectedAccount, account.id)
        await orchestrator.run_account_job(session, db_account, GITHUB_JOB)

    async with async_session_maker() as session:
        updated = await session.get(ConnectedAccount, account.id)
        assert updated.status == "paused"
        assert updated.meta["auth"]["reason"] == "meltano_auth_failure"


@pytest.mark.asyncio
async def test_meltano_failure_does_not_pause_connection(client, monkeypatch):
    account = await _seed_account()
    _patch_github(monkeypatch)

    async def fake_run(job, env, **kwargs):
        return meltano_runner.RunResult(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(orchestrator.meltano_runner, "run_job", fake_run)

    async with async_session_maker() as session:
        db_account = await session.get(ConnectedAccount, account.id)
        await orchestrator.run_account_job(session, db_account, GITHUB_JOB)

    async with async_session_maker() as session:
        updated = await session.get(ConnectedAccount, account.id)
        assert updated.status == "active"
        assert "auth" not in (updated.meta or {})
