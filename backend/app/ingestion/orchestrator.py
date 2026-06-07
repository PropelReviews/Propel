"""Ingestion orchestrator: drives Meltano per active connected_accounts row.

Run lifecycle per (account, job):
  1. overlap guard — skip if a run for this (account, resource_type) is running
  2. create ingestion_run (status=running)
  3. mint installation token; discover repos / org
  4. `meltano run <job>` (lands via target-propel)
  5. finalize: counts from DB, watermark cursor, status

Incrementality is driven by our own watermark (start_date), not Meltano state;
the datapoint partial unique indexes dedupe any re-pulled rows.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import async_session_maker
from app.ingestion import meltano_runner
from app.integrations.github import app_auth
from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    AuthType,
    ConnectionStatus,
    IngestionRunStatus,
    IntegrationProvider,
)
from app.models.ingestion_run import IngestionRun
from app.services import github_identity

logger = logging.getLogger("propel.ingestion")
settings = get_settings()

# Re-pull a day of overlap so provider restatements (e.g. updated PRs, Copilot's
# ~2-day restatement) are captured; dedupe handles the rest.
_WATERMARK_OVERLAP = timedelta(days=1)


@dataclass(frozen=True)
class JobSpec:
    name: str  # meltano job name
    resource_type: str  # ingestion_run.resource_type + overlap-guard key
    needs_repos: bool = False
    needs_org: bool = False  # requires the connected org login to run
    org_mode: str | None = None  # "array" (tap-github) | "copilot" (bare login)
    needs_member_logins: bool = False  # build TAP_GITHUB_USER_USERNAMES from roster


# Run order matters: org roster is synced before user profiles so the profile
# job can target the discovered logins.
JOBS: list[JobSpec] = [
    JobSpec("github_sync", "github", needs_repos=True),
    JobSpec(
        "github_org_sync",
        "github.org_members",
        needs_org=True,
        org_mode="array",
    ),
    JobSpec(
        "github_user_profiles_sync",
        "github.user_profiles",
        needs_org=True,
        needs_member_logins=True,
    ),
    JobSpec("copilot_sync", "copilot.usage", needs_org=True, org_mode="copilot"),
]

# Jobs after which the GitHub identity roster is reconciled into users/memberships.
_IDENTITY_SYNC_JOB = "github_user_profiles_sync"


def _ingestion_extra(
    account: ConnectedAccount,
    job: JobSpec,
    *,
    run: IngestionRun | None = None,
    **fields: object,
) -> dict[str, object]:
    extra: dict[str, object] = {
        "event": "extraction.run",
        "ingestion.job": job.name,
        "ingestion.resource_type": job.resource_type,
        "connected_account.id": str(account.id),
        "tenant.id": str(account.tenant_id),
    }
    if run is not None:
        extra["ingestion.run_id"] = str(run.id)
    extra.update(fields)
    return extra


async def run_all(
    *,
    account_id: uuid.UUID | None = None,
    job_name: str | None = None,
) -> None:
    """Entry point used by the CLI/cron. Iterates accounts and runs jobs."""
    jobs = [j for j in JOBS if job_name is None or j.name == job_name]
    if not jobs:
        logger.warning(
            "No ingestion job matches filter",
            extra={"event": "extraction.batch", "ingestion.job_filter": job_name},
        )
        return

    async with async_session_maker() as session:
        accounts = await _active_github_accounts(session, account_id)

    logger.info(
        "Ingestion batch starting",
        extra={
            "event": "extraction.batch",
            "ingestion.job_count": len(jobs),
            "ingestion.account_count": len(accounts),
            "ingestion.jobs": [job.name for job in jobs],
        },
    )
    if not accounts:
        logger.info(
            "No active GitHub connected accounts to ingest",
            extra={"event": "extraction.batch"},
        )
        return

    for account in accounts:
        for job in jobs:
            # Each (account, job) uses its own short-lived session so a failure
            # is isolated and the run row is always finalized.
            async with async_session_maker() as session:
                await run_account_job(session, account, job)

    logger.info(
        "Ingestion batch finished",
        extra={
            "event": "extraction.batch",
            "ingestion.job_count": len(jobs),
            "ingestion.account_count": len(accounts),
        },
    )


async def _active_github_accounts(
    session: AsyncSession, account_id: uuid.UUID | None
) -> list[ConnectedAccount]:
    query = select(ConnectedAccount).where(
        ConnectedAccount.provider == IntegrationProvider.github.value,
        ConnectedAccount.status == ConnectionStatus.active.value,
    )
    if account_id is not None:
        query = query.where(ConnectedAccount.id == account_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def run_account_job(
    session: AsyncSession, account: ConnectedAccount, job: JobSpec
) -> IngestionRun | None:
    if await _has_running(session, account.id, job.resource_type):
        logger.info(
            "Skipping extraction run: already in progress",
            extra=_ingestion_extra(
                account,
                job,
                status="skipped",
                skip_reason="overlap_guard",
            ),
        )
        return None

    run = IngestionRun(
        tenant_id=account.tenant_id,
        connected_account_id=account.id,
        source=IntegrationProvider.github.value,
        resource_type=job.resource_type,
        status=IngestionRunStatus.running.value,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    started_at = run.started_at or datetime.now(UTC)
    logger.info(
        "Extraction run started",
        extra=_ingestion_extra(account, job, run=run, status="running"),
    )
    try:
        env = await _build_env(session, account, job, run)
        if env is None:
            await _finalize(session, run, status=IngestionRunStatus.success)
            logger.info(
                "Extraction run skipped: nothing to ingest",
                extra=_ingestion_extra(
                    account,
                    job,
                    run=run,
                    status="success",
                    skip_reason="nothing_to_ingest",
                ),
            )
            return run

        result = await meltano_runner.run_job(job.name, env)
        if not result.ok:
            error = _tail(result.stderr or result.stdout)
            await _finalize(
                session,
                run,
                status=IngestionRunStatus.error,
                error=error,
            )
            fail_extra = _ingestion_extra(
                account, job, run=run, status="error"
            )
            fail_extra["process.returncode"] = result.returncode
            fail_extra["error.message"] = error
            logger.error(
                "Extraction run failed: Meltano exited non-zero",
                extra=fail_extra,
            )
            return run

        await _finalize(
            session,
            run,
            status=IngestionRunStatus.success,
            watermark=started_at,
        )
        duration_ms = _duration_ms(run.started_at, run.finished_at)
        complete_extra = _ingestion_extra(account, job, run=run, status="success")
        complete_extra["ingestion.records_pulled"] = run.records_pulled
        complete_extra["ingestion.datapoints_written"] = run.datapoints_written
        complete_extra["ingestion.duration_ms"] = duration_ms
        logger.info("Extraction run completed", extra=complete_extra)
        if job.name == _IDENTITY_SYNC_JOB:
            await _reconcile_identities(session, account)
    except Exception as exc:  # noqa: BLE001 — record failure on the run, keep going
        fail_extra = _ingestion_extra(account, job, run=run, status="error")
        fail_extra["error.message"] = str(exc)
        logger.exception("Extraction run failed", extra=fail_extra)
        await _finalize(session, run, status=IngestionRunStatus.error, error=str(exc))
    return run


async def _reconcile_identities(
    session: AsyncSession, account: ConnectedAccount
) -> None:
    """Map the freshly-synced GitHub org roster onto Propel users/memberships.

    Best-effort: the ingestion run has already succeeded, so a linking failure is
    logged but never marks the run as errored.
    """
    try:
        token = await app_auth.get_installation_token(account.external_account_id)
        admin_logins = await app_auth.list_org_admin_logins(
            token.token, account.external_account_name or ""
        )
        await github_identity.sync_and_link(session, account, admin_logins=admin_logins)
    except Exception:  # noqa: BLE001 — never fail ingestion on a linking error
        logger.exception(
            "GitHub identity reconciliation failed for account %s", account.id
        )


async def _has_running(
    session: AsyncSession, account_id: uuid.UUID, resource_type: str
) -> bool:
    result = await session.execute(
        select(IngestionRun.id).where(
            IngestionRun.connected_account_id == account_id,
            IngestionRun.resource_type == resource_type,
            IngestionRun.status == IngestionRunStatus.running.value,
        )
    )
    return result.first() is not None


async def _build_env(
    session: AsyncSession,
    account: ConnectedAccount,
    job: JobSpec,
    run: IngestionRun,
) -> dict[str, str] | None:
    """Build the per-run environment, or None to skip (nothing to ingest)."""
    if account.auth_type != AuthType.github_app_installation.value:
        skip_extra = _ingestion_extra(
            account, job, run=run, skip_reason="unsupported_auth_type"
        )
        skip_extra["connected_account.auth_type"] = account.auth_type
        logger.warning(
            "Skipping extraction run: unsupported auth type",
            extra=skip_extra,
        )
        return None

    token = await app_auth.get_installation_token(account.external_account_id)

    env: dict[str, str] = {
        "GITHUB_INSTALLATION_TOKEN": token.token,
        "PROPEL_DATABASE_URL": settings.sync_database_url,
        "PROPEL_TENANT_ID": str(account.tenant_id),
        "PROPEL_CONNECTED_ACCOUNT_ID": str(account.id),
        "PROPEL_RUN_ID": str(run.id),
        "PROPEL_SOURCE": IntegrationProvider.github.value,
    }

    if job.needs_repos:
        repos = await app_auth.list_installation_repositories(token.token)
        if not repos:
            logger.info(
                "Skipping extraction run: no accessible repositories",
                extra=_ingestion_extra(
                    account,
                    job,
                    run=run,
                    skip_reason="no_repositories",
                ),
            )
            return None
        env["TAP_GITHUB_REPOSITORIES"] = json.dumps(repos)
        env["TAP_GITHUB_START_DATE"] = await _start_date(
            session, account.id, job.resource_type
        )

    if job.needs_org and not account.external_account_name:
        logger.info(
            "Skipping extraction run: no org login on connected account",
            extra=_ingestion_extra(
                account,
                job,
                run=run,
                skip_reason="no_org_login",
            ),
        )
        return None

    if job.org_mode == "array":
        env["TAP_GITHUB_ORGANIZATIONS"] = json.dumps([account.external_account_name])
        env["TAP_GITHUB_START_DATE"] = await _start_date(
            session, account.id, job.resource_type
        )
    elif job.org_mode == "copilot":
        env["COPILOT_ORG"] = account.external_account_name

    if job.needs_member_logins:
        logins = await _member_logins(session, account)
        if not logins:
            logger.info(
                "Skipping extraction run: org members not synced yet",
                extra=_ingestion_extra(
                    account,
                    job,
                    run=run,
                    skip_reason="no_org_members",
                ),
            )
            return None
        env["TAP_GITHUB_USER_USERNAMES"] = json.dumps(logins)
        env["TAP_GITHUB_START_DATE"] = await _start_date(
            session, account.id, job.resource_type
        )

    return env


async def _member_logins(session: AsyncSession, account: ConnectedAccount) -> list[str]:
    """Logins from the most recent organization_members landing for this account.

    Reads back the roster that github_org_sync just wrote so the profile job can
    target exactly those users.
    """
    result = await session.execute(
        text(
            "SELECT DISTINCT payload->>'login' AS login "
            "FROM raw_record "
            "WHERE tenant_id = :tenant_id "
            "AND resource_type = 'organization_members' "
            "AND payload->>'login' IS NOT NULL"
        ),
        {"tenant_id": account.tenant_id},
    )
    return [row[0] for row in result.all()]


async def _start_date(
    session: AsyncSession, account_id: uuid.UUID, resource_type: str
) -> str:
    result = await session.execute(
        select(IngestionRun.cursor)
        .where(
            IngestionRun.connected_account_id == account_id,
            IngestionRun.resource_type == resource_type,
            IngestionRun.status == IngestionRunStatus.success.value,
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row and row.get("watermark"):
        watermark = datetime.fromisoformat(row["watermark"])
        return (watermark - _WATERMARK_OVERLAP).date().isoformat()
    backfill_start = datetime.now(UTC) - timedelta(
        days=settings.ingestion_backfill_days
    )
    return backfill_start.date().isoformat()


async def _finalize(
    session: AsyncSession,
    run: IngestionRun,
    *,
    status: IngestionRunStatus,
    error: str | None = None,
    watermark: datetime | None = None,
) -> None:
    records, datapoints = await _run_counts(session, run.id)
    run.status = status.value
    run.finished_at = datetime.now(UTC)
    run.records_pulled = records
    run.datapoints_written = datapoints
    run.error = error
    if watermark is not None:
        run.cursor = {"watermark": watermark.isoformat()}
    await session.commit()


async def _run_counts(session: AsyncSession, run_id: uuid.UUID) -> tuple[int, int]:
    records = await session.scalar(
        text("SELECT count(*) FROM raw_record WHERE run_id = :run_id"),
        {"run_id": run_id},
    )
    datapoints = await session.scalar(
        text(
            "SELECT count(*) FROM datapoint WHERE raw_record_id IN "
            "(SELECT id FROM raw_record WHERE run_id = :run_id)"
        ),
        {"run_id": run_id},
    )
    return int(records or 0), int(datapoints or 0)


def _tail(message: str, *, limit: int = 2000) -> str:
    message = (message or "").strip()
    return message[-limit:]


def _duration_ms(
    started_at: datetime | None, finished_at: datetime | None
) -> float | None:
    if started_at is None or finished_at is None:
        return None
    return round((finished_at - started_at).total_seconds() * 1000, 2)
