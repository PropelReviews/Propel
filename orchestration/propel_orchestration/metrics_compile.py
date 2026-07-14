"""Non-partitioned metrics compile job + dirty-set sensor (M4).

Activation / MetricSet changes mark rows in ``metric_compile_dirty``. The
``metrics_compile_dirty_sensor`` launches ``metrics_compile_build`` when the
dirty set is non-empty (single-flight via ``metric_compile_runs``). An hourly
schedule remains as a full-resolve backstop when ``METRICS_COMPILE_SOURCE=db``.

Note: no ``from __future__ import annotations`` — Dagster rejects stringified
context type hints (same constraint as analytics.py).
"""

import asyncio
import hashlib
import logging
import os
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit

from dagster import (
    DefaultScheduleStatus,
    DefaultSensorStatus,
    OpExecutionContext,
    RunRequest,
    ScheduleEvaluationContext,
    SensorEvaluationContext,
    SkipReason,
    job,
    op,
    schedule,
    sensor,
)

logger = logging.getLogger("propel.metrics_compile.dagster")


def _compile_source() -> str:
    return os.environ.get("METRICS_COMPILE_SOURCE", "files").strip().lower() or "files"


def _sync_database_url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    for prefix in ("postgresql+asyncpg://", "postgres://"):
        if raw.startswith(prefix):
            raw = "postgresql://" + raw[len(prefix) :]
            break
    return raw


def _dirty_fingerprint() -> tuple[int, str]:
    """Return (count, stable fingerprint) of metric_compile_dirty rows."""
    import psycopg2

    url = _sync_database_url()
    if not url:
        return 0, ""
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT content_hash FROM metric_compile_dirty ORDER BY content_hash"
            )
            hashes = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    if not hashes:
        return 0, ""
    digest = hashlib.sha256("\n".join(hashes).encode()).hexdigest()
    return len(hashes), digest


def _has_running_compile() -> bool:
    import psycopg2

    url = _sync_database_url()
    if not url:
        return False
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM metric_compile_runs WHERE status = 'running' LIMIT 1"
            )
            return cur.fetchone() is not None
    finally:
        conn.close()


@op
def metrics_compile_op(context: OpExecutionContext) -> None:
    """Claim single-flight compile and drain the dirty set (or full backstop)."""
    source = _compile_source()
    if source != "db":
        context.log.info(
            "Skipping metrics compile (METRICS_COMPILE_SOURCE=%s)", source
        )
        return

    full = context.run_tags.get("metrics_compile_full", "0") == "1"
    trigger = context.run_tags.get("metrics_compile_trigger", "dagster")

    try:
        from app.db.session import async_session_maker
        from app.services.metric_compile import run_compile
    except ImportError as exc:
        context.log.error("backend package unavailable: %s", exc)
        raise

    async def _run() -> dict:
        async with async_session_maker() as session:
            try:
                report = await run_compile(
                    session, full=full, trigger=trigger
                )
                await session.commit()
                return report
            except Exception:
                await session.rollback()
                raise

    report = asyncio.run(_run())
    context.log.info("metrics compile report: %s", report)


@job(name="metrics_compile_build")
def metrics_compile_build_job():
    metrics_compile_op()


_SOURCE_IS_DB = _compile_source() == "db"


@sensor(
    job=metrics_compile_build_job,
    minimum_interval_seconds=30,
    default_status=(
        DefaultSensorStatus.RUNNING
        if _SOURCE_IS_DB
        else DefaultSensorStatus.STOPPED
    ),
    description=(
        "Launch metrics_compile_build when metric_compile_dirty is non-empty "
        "and no compile run is already in flight."
    ),
)
def metrics_compile_dirty_sensor(context: SensorEvaluationContext):
    if _compile_source() != "db":
        return SkipReason("METRICS_COMPILE_SOURCE!=db")
    try:
        if _has_running_compile():
            return SkipReason("compile already running in metric_compile_runs")
        count, fingerprint = _dirty_fingerprint()
    except Exception as exc:  # noqa: BLE001 — sensor must not crash the daemon
        return SkipReason(f"could not read dirty set: {exc}")

    if count == 0:
        return SkipReason("dirty set empty")
    if fingerprint and fingerprint == context.cursor:
        return SkipReason("dirty set already requested")

    if fingerprint:
        context.update_cursor(fingerprint)
    return RunRequest(
        run_key=f"metrics-dirty:{fingerprint[:16] or 'empty'}",
        tags={
            "metrics_compile_trigger": "dirty_sensor",
            "metrics_compile_full": "0",
            "dirty_count": str(count),
        },
    )


@schedule(
    job=metrics_compile_build_job,
    cron_schedule="15 * * * *",
    default_status=(
        DefaultScheduleStatus.RUNNING
        if _SOURCE_IS_DB
        else DefaultScheduleStatus.STOPPED
    ),
)
def metrics_compile_hourly(context: ScheduleEvaluationContext):
    """Hourly full-resolve backstop when compiling from the definition store."""
    if _compile_source() != "db":
        return []
    _ = context
    return RunRequest(
        run_key=f"metrics-compile-full-{datetime.now(UTC).strftime('%Y%m%d%H')}",
        tags={
            "metrics_compile_trigger": "hourly",
            "metrics_compile_full": "1",
        },
    )


# Silence unused import warnings from URL helpers kept for parity with analytics.
_ = (unquote, urlsplit)
