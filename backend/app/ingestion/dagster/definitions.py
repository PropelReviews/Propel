"""Dagster job: one dynamic branch per org, sequential Meltano jobs per branch.

Each active GitHub connected_account gets its own subgraph:

    github_sync -> github_org_sync -> github_user_profiles_sync -> copilot_sync

The hourly schedule is evaluated by dagster-daemon (always-on ECS service).
"""

from __future__ import annotations

import asyncio
import uuid

from dagster import (
    Definitions,
    DynamicOut,
    DynamicOutput,
    ScheduleEvaluationContext,
    get_dagster_logger,
    graph,
    job,
    op,
    schedule,
)
from sqlalchemy import select

from app.db.session import async_session_maker
from app.ingestion.logging_config import (
    configure_ingestion_logging,
    shutdown_ingestion_logging,
)
from app.ingestion.orchestrator import JOBS, run_account_job
from app.models.connected_account import ConnectedAccount
from app.models.enums import ConnectionStatus, IntegrationProvider

_JOB_BY_NAME = {job.name: job for job in JOBS}


async def _active_account_ids() -> list[uuid.UUID]:
    async with async_session_maker() as session:
        result = await session.execute(
            select(ConnectedAccount.id).where(
                ConnectedAccount.provider == IntegrationProvider.github.value,
                ConnectedAccount.status == ConnectionStatus.active.value,
            )
        )
        return [row[0] for row in result.all()]


async def _run_job_for_account(account_id: uuid.UUID, job_name: str) -> None:
    job_spec = _JOB_BY_NAME[job_name]
    async with async_session_maker() as session:
        account = await session.get(ConnectedAccount, account_id)
        if account is None:
            raise ValueError(f"Connected account {account_id} not found")
        await run_account_job(session, account, job_spec)


def _run_job_sync(account_id: str, job_name: str) -> str:
    log = get_dagster_logger()
    otel_enabled = configure_ingestion_logging(service_name="propel-ingestion")
    extra = {
        "event": "extraction.dagster_op",
        "ingestion.job": job_name,
        "connected_account.id": account_id,
    }
    log.info("Dagster op starting", extra=extra)
    try:
        asyncio.run(_run_job_for_account(uuid.UUID(account_id), job_name))
        log.info("Dagster op finished", extra={**extra, "status": "success"})
        return account_id
    except Exception:
        log.exception("Dagster op failed", extra={**extra, "status": "error"})
        raise
    finally:
        shutdown_ingestion_logging(otel_enabled)


@op(out=DynamicOut(str))
def discover_active_accounts():
    log = get_dagster_logger()
    otel_enabled = configure_ingestion_logging(service_name="propel-ingestion")
    try:
        account_ids = asyncio.run(_active_account_ids())
        log.info(
            "Discovered active GitHub accounts",
            extra={
                "event": "extraction.discover",
                "ingestion.account_count": len(account_ids),
            },
        )
        for account_id in account_ids:
            key = str(account_id)
            yield DynamicOutput(key, mapping_key=key.replace("-", "_"))
    finally:
        shutdown_ingestion_logging(otel_enabled)


@op
def github_sync(account_id: str) -> str:
    return _run_job_sync(account_id, "github_sync")


@op
def github_org_sync(account_id: str) -> str:
    return _run_job_sync(account_id, "github_org_sync")


@op
def github_user_profiles_sync(account_id: str) -> str:
    return _run_job_sync(account_id, "github_user_profiles_sync")


@op
def copilot_sync(account_id: str) -> str:
    return _run_job_sync(account_id, "copilot_sync")


@graph
def org_ingestion_dag(account_id: str):
    """Per-org extraction DAG — order matches orchestrator.JOBS dependencies."""
    after_repos = github_sync(account_id)
    after_org = github_org_sync(after_repos)
    after_profiles = github_user_profiles_sync(after_org)
    copilot_sync(after_profiles)


@job
def ingestion_job():
    discover_active_accounts().map(org_ingestion_dag)


@schedule(cron_schedule="0 * * * *", job=ingestion_job, execution_timezone="UTC")
def hourly_ingestion_schedule(_context: ScheduleEvaluationContext):
    return {}


defs = Definitions(jobs=[ingestion_job], schedules=[hourly_ingestion_schedule])
