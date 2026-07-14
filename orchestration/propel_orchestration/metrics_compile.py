"""Non-partitioned metrics compile job (M4 dirty-set / shared models).

Runs independently of the per-tenant analytics dbt assets. When
``METRICS_COMPILE_SOURCE=db``, the backend marks content hashes dirty on
activation; this job (or an API-triggered run) regenerates shared models.

Note: no ``from __future__ import annotations`` — Dagster rejects stringified
context type hints (same constraint as analytics.py).
"""

import asyncio
import logging
import os
from datetime import UTC, datetime

from dagster import (
    DefaultScheduleStatus,
    OpExecutionContext,
    RunRequest,
    ScheduleEvaluationContext,
    job,
    op,
    schedule,
)

logger = logging.getLogger("propel.metrics_compile.dagster")


@op
def metrics_compile_op(context: OpExecutionContext) -> None:
    """Resolve all orgs and regenerate dirty shared metric models.

    Skips when ``METRICS_COMPILE_SOURCE`` is not ``db`` (default ``files``).
    """
    source = os.environ.get("METRICS_COMPILE_SOURCE", "files").strip().lower()
    if source != "db":
        context.log.info(
            "Skipping metrics compile (METRICS_COMPILE_SOURCE=%s)", source
        )
        return

    # Import inside the op so the webserver can load definitions without the
    # backend package on the path in all environments.
    try:
        from app.db.session import async_session_maker
        from app.services.metric_compile import run_compile
    except ImportError as exc:
        context.log.error("backend package unavailable: %s", exc)
        raise

    async def _run() -> dict:
        async with async_session_maker() as session:
            return await run_compile(session, full=False)

    report = asyncio.run(_run())
    context.log.info("metrics compile report: %s", report)


@job(name="metrics_compile_build")
def metrics_compile_build_job():
    metrics_compile_op()


@schedule(
    job=metrics_compile_build_job,
    cron_schedule="15 * * * *",
    default_status=DefaultScheduleStatus.STOPPED,
)
def metrics_compile_hourly(context: ScheduleEvaluationContext):
    """Hourly dirty-set compile backstop (enable in prod when source=db)."""
    _ = context
    return RunRequest(
        run_key=f"metrics-compile-{datetime.now(UTC).strftime('%Y%m%d%H')}"
    )
