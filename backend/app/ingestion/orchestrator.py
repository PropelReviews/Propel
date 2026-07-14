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

import contextlib
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import async_session_maker
from app.ingestion import meltano_runner
from app.integrations.github import app_auth, copilot
from app.integrations.linear.oauth import LinearOAuthError
from app.models.connected_account import ConnectedAccount
from app.models.enums import (
    AuthType,
    ConnectionStatus,
    IngestionRunStatus,
    IntegrationProvider,
)
from app.models.ingestion_run import IngestionRun
from app.services import connections as connection_service
from app.services import github_identity
from app.services.token_crypto import TokenEncryptionError

logger = logging.getLogger("propel.ingestion")
settings = get_settings()

# Re-pull a day of overlap so provider restatements (e.g. updated PRs, Copilot's
# ~2-day restatement) are captured; dedupe handles the rest.
_WATERMARK_OVERLAP = timedelta(days=1)

# A run still marked `running` after this long is assumed dead (its worker was
# killed mid-run — ECS deploy, OOM, timeout). Left untouched it would block the
# overlap guard forever; we mark it `error` at the start of every batch so the
# next run can proceed.
_STALE_RUN_MAX_AGE = timedelta(hours=2)

# Copilot availability is probed at most once per TTL per account; the result is
# cached on connected_accounts.metadata so orgs without Copilot skip the sync
# without an extra GitHub call every hour.
_COPILOT_CHECK_TTL = timedelta(hours=24)
_COPILOT_META_KEY = "copilot_metrics"


@dataclass(frozen=True)
class JobSpec:
    name: str  # meltano job name
    resource_type: str  # ingestion_run.resource_type + overlap-guard key
    provider: str = IntegrationProvider.github.value  # owning data source
    needs_repos: bool = False
    needs_org: bool = False  # requires the connected org login to run
    org_mode: str | None = None  # "array" (tap-github) | "copilot" (bare login)
    needs_member_logins: bool = False  # build TAP_GITHUB_USER_USERNAMES from roster


# Run order matters: org roster is synced before user profiles so the profile
# job can target the discovered logins. Repo activity is split per resource
# (commits / pull_requests / issues) so each is its own granular run with an
# independent watermark and failure boundary.
JOBS: list[JobSpec] = [
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
    JobSpec("github_commits_sync", "github.commits", needs_repos=True),
    JobSpec("github_pull_requests_sync", "github.pull_requests", needs_repos=True),
    JobSpec("github_issues_sync", "github.issues", needs_repos=True),
    JobSpec("github_releases_sync", "github.releases", needs_repos=True),
    JobSpec(
        "github_workflow_runs_sync",
        "github.workflow_runs",
        needs_repos=True,
    ),
    JobSpec("copilot_sync", "copilot.usage", needs_org=True, org_mode="copilot"),
    JobSpec(
        "linear_issues_sync",
        "linear.issues",
        provider=IntegrationProvider.linear.value,
    ),
    JobSpec(
        "linear_comments_sync",
        "linear.comments",
        provider=IntegrationProvider.linear.value,
    ),
    JobSpec(
        "linear_projects_sync",
        "linear.projects",
        provider=IntegrationProvider.linear.value,
    ),
    JobSpec(
        "linear_description_edits_sync",
        "linear.description_edits",
        provider=IntegrationProvider.linear.value,
    ),
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
    start_date: str | None = None,
) -> list[IngestionRun]:
    """Run the matching jobs for the matching accounts.

    Scopes to a single org when ``account_id`` is set (the per-org Dagster runs
    pass it from the run tags); with ``account_id=None`` it processes every
    active account (manual "run everything"). ``start_date`` (ISO date)
    overrides the stored watermark for time-based backfills — the taps re-pull
    everything since that date and the DB-level dedupe absorbs the overlap.
    Returns the ``IngestionRun`` rows that actually executed (overlap-skipped
    runs are omitted) so callers can report per-resource outcomes (e.g. Dagster
    asset materializations).
    """
    jobs = [j for j in JOBS if job_name is None or j.name == job_name]
    if not jobs:
        logger.warning(
            "No ingestion job matches filter",
            extra={"event": "extraction.batch", "ingestion.job_filter": job_name},
        )
        return []

    async with async_session_maker() as session:
        await _clear_stale_runs(session)

    # Jobs may span providers (GitHub + Linear); list accounts per provider so a
    # GitHub-scoped account is never paired with a Linear job (and vice versa).
    providers = {job.provider for job in jobs}
    runs: list[IngestionRun] = []
    for provider in sorted(providers):
        provider_jobs = [job for job in jobs if job.provider == provider]
        async with async_session_maker() as session:
            accounts = await _active_accounts(session, account_id, provider)

        logger.info(
            "Ingestion batch starting",
            extra={
                "event": "extraction.batch",
                "ingestion.provider": provider,
                "ingestion.job_count": len(provider_jobs),
                "ingestion.account_count": len(accounts),
                "ingestion.jobs": [job.name for job in provider_jobs],
                "ingestion.account_ids": [str(account.id) for account in accounts],
                "ingestion.org_logins": [
                    account.external_account_name for account in accounts
                ],
            },
        )
        if not accounts:
            logger.info(
                "No active connected accounts to ingest",
                extra={"event": "extraction.batch", "ingestion.provider": provider},
            )
            continue

        for account in accounts:
            for job in provider_jobs:
                # Each (account, job) uses its own short-lived session so a
                # failure is isolated and the run row is always finalized.
                async with async_session_maker() as session:
                    run = await run_account_job(
                        session, account, job, start_date_override=start_date
                    )
                if run is not None:
                    runs.append(run)

    logger.info(
        "Ingestion batch finished",
        extra={
            "event": "extraction.batch",
            "ingestion.job_count": len(jobs),
            "ingestion.run_count": len(runs),
        },
    )
    return runs


async def _active_accounts(
    session: AsyncSession,
    account_id: uuid.UUID | None,
    provider: str = IntegrationProvider.github.value,
) -> list[ConnectedAccount]:
    query = select(ConnectedAccount).where(
        ConnectedAccount.provider == provider,
        ConnectedAccount.status == ConnectionStatus.active.value,
    )
    if account_id is not None:
        query = query.where(ConnectedAccount.id == account_id)
    result = await session.execute(query)
    return list(result.scalars().all())


async def _sync_installations() -> None:
    """Reconcile connected_accounts with the App's installations on GitHub.

    Best effort: a GitHub outage must not block ingestion of already-known
    accounts, so failures are logged and swallowed.
    """
    from app.services import connections as connection_service

    try:
        async with async_session_maker() as session:
            await connection_service.sync_installations_from_github(session)
    except Exception:  # noqa: BLE001 — discovery must not block ingestion
        logger.exception(
            "GitHub installation sync failed; continuing with known accounts",
            extra={"event": "extraction.discover"},
        )


async def discover_installed_orgs(account_id: uuid.UUID | None = None) -> int:
    """Sync and log the connected GitHub orgs (installations) we will ingest.

    This is the first step in the granular Dagster DAG ("get installed orgs").
    For unscoped runs it first reconciles connected_accounts against the App's
    installations on GitHub, so installing the app is all an org needs to be
    ingested. Returns the number of active accounts.
    """
    if account_id is None:
        await _sync_installations()
    async with async_session_maker() as session:
        accounts = await _active_accounts(session, account_id)

    logger.info(
        "Discovered installed GitHub orgs",
        extra={
            "event": "extraction.discover",
            "ingestion.account_count": len(accounts),
            "ingestion.account_ids": [str(account.id) for account in accounts],
            "ingestion.org_logins": [
                account.external_account_name for account in accounts
            ],
        },
    )
    return len(accounts)


async def list_active_accounts(
    account_id: uuid.UUID | None = None,
    provider: str = IntegrationProvider.github.value,
) -> list[tuple[str, str | None]]:
    """Return ``(account_id, account_name)`` for active accounts of ``provider``.

    Used by the Dagster schedule to fan out one run per account. For GitHub,
    unscoped calls first sync installations so newly installed orgs are picked
    up without any manual step; other providers (e.g. Linear) are provisioned
    by their OAuth connect flow, so no external sync is needed. Returns plain
    tuples (not ORM rows) so the caller can use them after the session closes.
    """
    if account_id is None and provider == IntegrationProvider.github.value:
        await _sync_installations()
    async with async_session_maker() as session:
        accounts = await _active_accounts(session, account_id, provider)
    return [(str(account.id), account.external_account_name) for account in accounts]


async def run_account_job(
    session: AsyncSession,
    account: ConnectedAccount,
    job: JobSpec,
    *,
    start_date_override: str | None = None,
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
        source=account.provider,
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
        env = await _build_env(
            session, account, job, run, start_date_override=start_date_override
        )
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

        _log_env_built(account, job, run, env)

        result = await meltano_runner.run_job(job.name, env)
        if not result.ok:
            raw_error = result.stderr or result.stdout or ""
            error = _summarize_error(raw_error)
            await _finalize(
                session,
                run,
                status=IngestionRunStatus.error,
                error=error,
            )
            fail_extra = _ingestion_extra(account, job, run=run, status="error")
            fail_extra["process.returncode"] = result.returncode
            fail_extra["error.message"] = error
            logger.error(
                "Extraction run failed: Meltano exited non-zero",
                extra=fail_extra,
            )
            if _looks_like_auth_failure(raw_error):
                await _mark_auth_failure_from_message(
                    session,
                    account,
                    reason="meltano_auth_failure",
                    message=_auth_failure_user_message(account, raw_error),
                    status=_meltano_auth_status(account, raw_error),
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
        await _pause_on_auth_failure(session, account, exc)
    return run


_AUTH_ERROR_MARKERS = (
    "401",
    "403",
    "unauthorized",
    "authentication",
    "invalid_token",
    "invalid token",
    "token has been revoked",
    "bad credentials",
    "access denied",
    "not authenticated",
    "forbidden",
    "invalid_grant",
    "auth_token",
    "oauth",
)


def _strip_ansi(message: str) -> str:
    # Meltano Rich traces include ANSI; strip so classification / UI stay readable.
    return re.sub(r"\x1b\[[0-9;]*m", "", message or "")


def _looks_like_auth_failure(message: str) -> bool:
    text = _strip_ansi(message).lower()
    return any(marker in text for marker in _AUTH_ERROR_MARKERS)


def _meltano_auth_status(account: ConnectedAccount, message: str) -> ConnectionStatus:
    text = _strip_ansi(message).lower()
    if account.provider == IntegrationProvider.github.value and "404" in text:
        return ConnectionStatus.revoked
    return ConnectionStatus.paused


def _auth_failure_user_message(account: ConnectedAccount, message: str) -> str:
    status = _meltano_auth_status(account, message)
    if status == ConnectionStatus.revoked:
        return "GitHub App installation is missing or inaccessible. Reinstall the app."
    if account.provider == IntegrationProvider.linear.value:
        return "Linear authentication failed during ingestion. Reconnect Linear."
    return (
        "GitHub App authentication failed during ingestion. "
        "Reinstall or check the app installation."
    )


def _summarize_error(message: str, *, limit: int = 2000) -> str:
    """Prefer root-cause lines over Meltano's Rich CLI footer."""
    cleaned = _strip_ansi(message).strip()
    if not cleaned:
        return ""
    lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
    interesting = [
        ln
        for ln in lines
        if any(
            key in ln.lower()
            for key in (
                "error",
                "exception",
                "failed",
                "401",
                "403",
                "404",
                "unauthorized",
                "forbidden",
                "graphql",
                "traceback",
            )
        )
    ]
    body = "\n".join(interesting[-50:] if interesting else lines[-50:])
    return body[-limit:]


def _auth_failure_status(exc: BaseException) -> ConnectionStatus | None:
    """Map auth exceptions to a connection status, or None if not an auth issue."""
    if isinstance(exc, (LinearOAuthError, TokenEncryptionError)):
        return ConnectionStatus.paused
    if isinstance(exc, app_auth.GitHubAppAuthError):
        # 404 on installation token exchange usually means the app was removed.
        message = str(exc)
        if "(404)" in message:
            return ConnectionStatus.revoked
        return ConnectionStatus.paused
    return None


async def _mark_auth_failure_from_message(
    session: AsyncSession,
    account: ConnectedAccount,
    *,
    reason: str,
    message: str,
    status: ConnectionStatus,
) -> None:
    db_account = await session.get(ConnectedAccount, account.id)
    if db_account is None:
        return
    connection_service.mark_auth_failure(
        db_account, reason=reason, message=message, status=status
    )
    await session.commit()
    logger.warning(
        "Paused connection after auth failure",
        extra={
            "event": "connection.auth_failure",
            "connected_account.id": str(db_account.id),
            "tenant.id": str(db_account.tenant_id),
            "connection.provider": db_account.provider,
            "connection.status": db_account.status,
            "error.message": message,
            "error.reason": reason,
        },
    )


async def _pause_on_auth_failure(
    session: AsyncSession,
    account: ConnectedAccount,
    exc: BaseException,
) -> None:
    """Pause/revoke the connection when ingestion fails due to install/auth state.

    Generic Meltano errors are ignored unless they look like auth failures —
    only token/install auth issues flip the connection so the workspace
    Integrations UI can prompt reconnect.
    """
    status = _auth_failure_status(exc)
    if status is None:
        return
    message = (
        "GitHub App installation is missing or inaccessible. Reinstall the app."
        if status == ConnectionStatus.revoked
        else (
            "Authentication failed during ingestion. Reconnect this integration."
            if isinstance(exc, (LinearOAuthError, TokenEncryptionError))
            else "GitHub App authentication failed during ingestion. "
            "Reinstall or check the app installation."
        )
    )
    await _mark_auth_failure_from_message(
        session,
        account,
        reason=type(exc).__name__,
        message=message,
        status=status,
    )


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


def _log_env_built(
    account: ConnectedAccount,
    job: JobSpec,
    run: IngestionRun,
    env: dict[str, str],
) -> None:
    """Log what the run will actually pull, so 0-record runs are explainable."""
    extra = _ingestion_extra(account, job, run=run, status="running")
    extra["event"] = "ingestion.env_built"

    repos_raw = env.get("TAP_GITHUB_REPOSITORIES")
    if repos_raw:
        with contextlib.suppress(ValueError, TypeError):
            extra["ingestion.repository_count"] = len(json.loads(repos_raw))
    members_raw = env.get("TAP_GITHUB_USER_USERNAMES")
    if members_raw:
        with contextlib.suppress(ValueError, TypeError):
            extra["ingestion.member_login_count"] = len(json.loads(members_raw))
    start_date = env.get("TAP_GITHUB_START_DATE") or env.get("TAP_LINEAR_START_DATE")
    if start_date:
        extra["ingestion.start_date"] = start_date
    if env.get("COPILOT_ORG"):
        extra["ingestion.copilot_org"] = env["COPILOT_ORG"]

    logger.info("Extraction environment built", extra=extra)


async def _clear_stale_runs(
    session: AsyncSession, max_age: timedelta = _STALE_RUN_MAX_AGE
) -> int:
    """Mark long-stuck `running` runs as `error` so the overlap guard unblocks.

    A worker killed mid-run never finalizes its ingestion_run row; the leftover
    `running` status then makes `_has_running` skip every future run for that
    (account, resource_type). Reaping them here makes ingestion self-heal.
    """
    cutoff = datetime.now(UTC) - max_age
    result = await session.execute(
        select(IngestionRun).where(
            IngestionRun.status == IngestionRunStatus.running.value,
            IngestionRun.started_at < cutoff,
        )
    )
    stale = list(result.scalars().all())
    if not stale:
        return 0

    finished_at = datetime.now(UTC)
    for run in stale:
        run.status = IngestionRunStatus.error.value
        run.finished_at = finished_at
        run.error = "stale run cleanup: exceeded max age while still running"
    await session.commit()

    logger.warning(
        "Cleared stale ingestion runs",
        extra={
            "event": "ingestion.stale_runs_cleared",
            "ingestion.stale_runs_cleared": len(stale),
            "ingestion.stale_run_ids": [str(run.id) for run in stale],
        },
    )
    return len(stale)


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
    *,
    start_date_override: str | None = None,
) -> dict[str, str] | None:
    """Build the per-run environment, or None to skip (nothing to ingest).

    ``start_date_override`` (ISO date) replaces the watermark-derived start date
    for time-based backfills. Dispatches per provider.
    """
    if job.provider == IntegrationProvider.linear.value:
        return await _build_linear_env(
            session, account, job, run, start_date_override=start_date_override
        )
    return await _build_github_env(
        session, account, job, run, start_date_override=start_date_override
    )


async def _build_linear_env(
    session: AsyncSession,
    account: ConnectedAccount,
    job: JobSpec,
    run: IngestionRun,
    *,
    start_date_override: str | None = None,
) -> dict[str, str] | None:
    from app.services import linear_connection

    if account.auth_type != AuthType.oauth.value:
        skip_extra = _ingestion_extra(
            account, job, run=run, skip_reason="unsupported_auth_type"
        )
        skip_extra["connected_account.auth_type"] = account.auth_type
        logger.warning(
            "Skipping extraction run: unsupported auth type", extra=skip_extra
        )
        return None

    access_token = await linear_connection.get_access_token(session, account)
    start_date = start_date_override or await _start_date(
        session, account.id, job.resource_type
    )
    return {
        "PROPEL_DATABASE_URL": settings.sync_database_url,
        "PROPEL_TENANT_ID": str(account.tenant_id),
        "PROPEL_CONNECTED_ACCOUNT_ID": str(account.id),
        "PROPEL_RUN_ID": str(run.id),
        "PROPEL_SOURCE": IntegrationProvider.linear.value,
        "TAP_LINEAR_AUTH_TOKEN": access_token,
        "TAP_LINEAR_START_DATE": start_date,
    }


async def _build_github_env(
    session: AsyncSession,
    account: ConnectedAccount,
    job: JobSpec,
    run: IngestionRun,
    *,
    start_date_override: str | None = None,
) -> dict[str, str] | None:
    async def resolved_start_date() -> str:
        if start_date_override:
            return start_date_override
        return await _start_date(session, account.id, job.resource_type)

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
        env["TAP_GITHUB_START_DATE"] = await resolved_start_date()

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
        env["TAP_GITHUB_START_DATE"] = await resolved_start_date()
    elif job.org_mode == "copilot":
        if not await _copilot_available(session, account, token.token):
            logger.info(
                "Skipping extraction run: Copilot metrics not available for org",
                extra=_ingestion_extra(
                    account,
                    job,
                    run=run,
                    skip_reason="copilot_not_available",
                ),
            )
            return None
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
        env["TAP_GITHUB_START_DATE"] = await resolved_start_date()

    return env


async def _copilot_available(
    session: AsyncSession, account: ConnectedAccount, token: str
) -> bool:
    """Whether the org exposes Copilot metrics, cached on the account metadata.

    A fresh cached answer (within ``_COPILOT_CHECK_TTL``) is used as-is; missing
    or stale entries trigger a re-probe whose result is persisted, so orgs that
    enable Copilot later are picked up within a day.
    """
    db_account = await session.get(ConnectedAccount, account.id) or account
    cached = (db_account.meta or {}).get(_COPILOT_META_KEY) or {}
    checked_at_raw = cached.get("checked_at")
    if isinstance(cached.get("available"), bool) and checked_at_raw:
        with contextlib.suppress(ValueError, TypeError):
            checked_at = datetime.fromisoformat(checked_at_raw)
            if datetime.now(UTC) - checked_at < _COPILOT_CHECK_TTL:
                return cached["available"]

    available = await copilot.copilot_metrics_available(
        token, account.external_account_name or ""
    )
    # Reassign (not mutate) the JSONB dict so SQLAlchemy detects the change.
    db_account.meta = {
        **(db_account.meta or {}),
        _COPILOT_META_KEY: {
            "available": available,
            "checked_at": datetime.now(UTC).isoformat(),
        },
    }
    await session.commit()
    return available


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
