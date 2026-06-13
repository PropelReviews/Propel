"""Dagster jobs, schedule, and fan-out sensor that drive Propel ingestion.

The pipeline is an event-driven job chain (no per-org cron):

1. ``discovery_job`` — hourly (``discovery_schedule``). Reconciles
   ``connected_accounts`` against the GitHub App's installations, so installing
   the app is all an org needs to be ingested.
2. ``org_ingestion_job`` — one run **per org**, launched by
   ``org_fanout_sensor`` when a discovery run succeeds. Each run is tagged with
   the org's ``connected_account`` id, so a failure or slow org is isolated to
   its own run and shows up as its own entry in the Dagster UI / PostHog
   (service ``propel-ingestion``). Launching the job manually with no tag falls
   back to processing every active org in a single run.
3. Analytics — ``analytics_sensor`` (see ``analytics.py``) fires a
   tenant-partitioned dbt run whenever an ``org_ingestion_job`` run succeeds.

DAG shape (per org)::

    start_org_ingestion ─┬─> get_org_members ──> get_user_profiles ─┐
                         ├─> get_commits ───────────────────────────┤
                         ├─> get_pull_requests ──────────────────────┤
                         ├─> get_issues ─────────────────────────────┤
                         └─> get_copilot_usage ──────────────────────┴─> flush_logs

``get_user_profiles`` runs after ``get_org_members`` (it targets the member
logins discovered by the roster sync). The repo-activity ops and Copilot only
need the installed org. Each resource op emits an ``AssetMaterialization`` per
``ingestion_run`` so the Assets catalog shows what landed (records pulled,
datapoints written) per resource. ``flush_logs`` fans in last to drain the OTLP
batch handler before the run worker process exits.

Backfills: ingestion is incremental (watermark per account/resource with a
1-day overlap; DB-level dedupe). To re-pull history, launch
``org_ingestion_job`` with the ``propel/start_date`` tag (ISO date) — it
overrides the watermark and the analytics sensor recomputes the tenant's
metrics afterwards automatically.
"""

import asyncio
import contextlib
import logging
import shutil
import time
import uuid
from datetime import date

from dagster import (
    AssetKey,
    AssetMaterialization,
    DagsterRunStatus,
    DefaultScheduleStatus,
    DefaultSensorStatus,
    In,
    MetadataValue,
    Nothing,
    OpExecutionContext,
    Out,
    RunRequest,
    RunsFilter,
    RunStatusSensorContext,
    ScheduleEvaluationContext,
    SensorEvaluationContext,
    SkipReason,
    in_process_executor,
    job,
    op,
    run_status_sensor,
    schedule,
    sensor,
)

from propel_orchestration import worker_scaling
from propel_orchestration.dask_resource import build_dask_executor

logger = logging.getLogger("propel.ingestion.dagster")

# Run tags carrying the per-org scope (set by the fan-out sensor's RunRequests)
# and the optional backfill start-date override.
_ACCOUNT_TAG = "propel/account_id"
_ORG_TAG = "propel/org"
_START_DATE_TAG = "propel/start_date"

# Asset key per Meltano job, so the Assets catalog has one node per GitHub
# resource (materialized per org on every run).
_ASSET_KEYS: dict[str, AssetKey] = {
    "github_org_sync": AssetKey(["github", "org_members"]),
    "github_user_profiles_sync": AssetKey(["github", "user_profiles"]),
    "github_commits_sync": AssetKey(["github", "commits"]),
    "github_pull_requests_sync": AssetKey(["github", "pull_requests"]),
    "github_issues_sync": AssetKey(["github", "issues"]),
    "copilot_sync": AssetKey(["github", "copilot_usage"]),
    "linear_issues_sync": AssetKey(["linear", "issues"]),
}

_event_loop: asyncio.AbstractEventLoop | None = None


def _run(coro):
    """Run a coroutine on a single process-wide event loop.

    The backend's async SQLAlchemy engine binds its connection pool to the
    first running loop, so every op executing in a given process must share
    one loop — ``asyncio.run()`` (a fresh loop per op) reuses pooled
    connections across loops and raises "got Future attached to a different
    loop". This holds for ``in_process_executor`` (all ops in one process) and
    for Dask workers (each long-lived worker process may run many steps).
    """
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop.run_until_complete(coro)


def _run_tags(context: OpExecutionContext) -> dict[str, str]:
    tags = getattr(context, "run_tags", None)
    if tags is None:
        run = getattr(context, "run", None)
        tags = getattr(run, "tags", {}) or {}
    return tags


def _run_scope(context: OpExecutionContext) -> tuple[uuid.UUID | None, str | None]:
    """Resolve the (account_id, org) this run is scoped to from its run tags."""
    tags = _run_tags(context)
    raw = tags.get(_ACCOUNT_TAG)
    org = tags.get(_ORG_TAG) or None
    account_id = uuid.UUID(raw) if raw else None
    return account_id, org


def _start_date_override(context: OpExecutionContext) -> str | None:
    """Resolve the backfill start-date override from the run tags, if any."""
    raw = _run_tags(context).get(_START_DATE_TAG)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        context.log.warning(
            f"Ignoring invalid {_START_DATE_TAG} tag {raw!r} (expected ISO date)"
        )
        return None


async def _log_startup_diagnostics() -> None:
    """Log environment readiness so 0-record runs are explainable from logs."""
    from sqlalchemy import text

    from app.config import get_settings
    from app.db.session import async_session_maker

    settings = get_settings()

    db_ok = False
    db_error: str | None = None
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:  # noqa: BLE001 — diagnostic only, never raise
        db_error = str(exc)

    extra: dict[str, object] = {
        "event": "ingestion.startup",
        "ingestion.meltano_installed": shutil.which("meltano") is not None,
        "ingestion.github_app_configured": bool(settings.github_app_id),
        "ingestion.posthog_configured": bool(settings.posthog_token),
        "ingestion.database_reachable": db_ok,
    }
    if db_error is not None:
        extra["error.message"] = db_error

    if db_ok:
        logger.info("Ingestion startup diagnostics", extra=extra)
    else:
        logger.error(
            "Ingestion startup diagnostics: database unreachable", extra=extra
        )


def _run_resource(context: OpExecutionContext, job_name: str) -> None:
    """Run one Meltano job for this run's org(s) and materialize the results."""
    from app.ingestion import orchestrator

    account_id, org = _run_scope(context)
    start_date = _start_date_override(context)
    started = time.monotonic()
    run_extra = {
        "event": "dagster.op",
        "dagster.run_id": context.run_id,
        "ingestion.job": job_name,
        "ingestion.org": org or "all",
    }
    if start_date:
        run_extra["ingestion.start_date_override"] = start_date
    context.log.info(f"Running {job_name} for {org or 'all active orgs'}")
    logger.info("Ingestion resource starting", extra=run_extra)
    try:
        runs = _run(
            orchestrator.run_all(
                account_id=account_id, job_name=job_name, start_date=start_date
            )
        )
    except Exception as exc:
        logger.exception(
            "Ingestion resource failed",
            extra={**run_extra, "dagster.status": "error", "error.message": str(exc)},
        )
        raise

    asset_key = _ASSET_KEYS.get(job_name)
    for run in runs or []:
        if asset_key is not None:
            context.log_event(
                AssetMaterialization(
                    asset_key=asset_key,
                    description=f"{job_name} ({org or run.connected_account_id})",
                    metadata={
                        "org": org or "",
                        "account_id": str(run.connected_account_id),
                        "status": run.status,
                        "records_pulled": MetadataValue.int(run.records_pulled or 0),
                        "datapoints_written": MetadataValue.int(
                            run.datapoints_written or 0
                        ),
                        "ingestion_run_id": str(run.id),
                    },
                )
            )

    duration_ms = round((time.monotonic() - started) * 1000, 2)
    logger.info(
        "Ingestion resource completed",
        extra={
            **run_extra,
            "dagster.status": "success",
            "ingestion.duration_ms": duration_ms,
            "ingestion.run_count": len(runs or []),
        },
    )


@op(
    out=Out(Nothing),
    description="Sync GitHub App installations into connected_accounts.",
)
def discover_orgs(context: OpExecutionContext) -> None:
    from app.ingestion import orchestrator

    async def _discover() -> int:
        await _log_startup_diagnostics()
        return await orchestrator.discover_installed_orgs(None)

    count = _run(_discover())
    context.log.info(f"Discovered {count} active GitHub org(s)")


@op(
    out=Out(Nothing),
    description="Validate this run's org scope and log startup diagnostics.",
)
def start_org_ingestion(context: OpExecutionContext) -> None:
    _account_id, org = _run_scope(context)
    start_date = _start_date_override(context)
    scope = org or "all active orgs"
    suffix = f" (backfill since {start_date})" if start_date else ""
    context.log.info(f"Starting ingestion run for: {scope}{suffix}")
    _run(_log_startup_diagnostics())


def _resource_op(op_name: str, job_name: str, description: str):
    """Build a per-resource op that depends on upstream via a Nothing input."""

    @op(
        name=op_name,
        ins={"start": In(Nothing)},
        out=Out(Nothing),
        description=description,
    )
    def _resource(context: OpExecutionContext) -> None:
        _run_resource(context, job_name)

    return _resource


get_org_members = _resource_op(
    "get_org_members",
    "github_org_sync",
    "Sync the organization member roster for the org.",
)
get_user_profiles = _resource_op(
    "get_user_profiles",
    "github_user_profiles_sync",
    "Enrich user profiles for the discovered org members.",
)
get_commits = _resource_op(
    "get_commits",
    "github_commits_sync",
    "Pull commits across the org's repositories.",
)
get_pull_requests = _resource_op(
    "get_pull_requests",
    "github_pull_requests_sync",
    "Pull pull requests, reviews, and review comments across the org's repos.",
)
get_issues = _resource_op(
    "get_issues",
    "github_issues_sync",
    "Pull issues and issue comments across the org's repos.",
)
get_copilot_usage = _resource_op(
    "get_copilot_usage",
    "copilot_sync",
    "Pull GitHub Copilot usage metrics for the org.",
)
get_linear_issues = _resource_op(
    "get_linear_issues",
    "linear_issues_sync",
    "Pull issues for the connected Linear workspace.",
)


@op(
    ins={"after": In(Nothing)},
    description="Flush the OTLP batch handler before the run worker process exits.",
)
def flush_logs(context: OpExecutionContext) -> None:
    # Dispose the async engine on the shared loop so pooled connections close
    # cleanly before the worker process exits.
    with contextlib.suppress(Exception):
        from app.db.session import engine

        _run(engine.dispose())
    with contextlib.suppress(Exception):
        from app.otel_logging import shutdown_logging

        shutdown_logging()


@job(
    executor_def=in_process_executor,
    description="Get installed GitHub orgs (App installations -> connected_accounts).",
)
def discovery_job() -> None:
    discover_orgs()


# Steps execute on the shared Dask worker fleet (DASK_SCHEDULER_ADDRESS), so
# concurrent per-org runs share worker capacity instead of stacking Meltano
# subprocesses on the daemon's task. Falls back to a per-run LocalCluster when
# no scheduler is configured (bare `dagster dev`).
@job(
    executor_def=build_dask_executor(),
    description=(
        "Pull one org's raw GitHub data (scoped by the propel/account_id tag; "
        "tag propel/start_date for a time-based backfill)."
    ),
)
def org_ingestion_job() -> None:
    started = start_org_ingestion()
    members = get_org_members(start=started)
    profiles = get_user_profiles(start=members)
    commits = get_commits(start=started)
    pulls = get_pull_requests(start=started)
    issues = get_issues(start=started)
    copilot = get_copilot_usage(start=started)
    flush_logs(after=[profiles, commits, pulls, issues, copilot])


@job(
    executor_def=build_dask_executor(),
    description=(
        "Pull one Linear workspace's issues (scoped by the propel/account_id "
        "tag; tag propel/start_date for a time-based backfill)."
    ),
)
def linear_ingestion_job() -> None:
    started = start_org_ingestion()
    issues = get_linear_issues(start=started)
    flush_logs(after=[issues])


async def _list_accounts(
    account_id: uuid.UUID | None = None, provider: str = "github"
):
    from app.ingestion import orchestrator

    return await orchestrator.list_active_accounts(account_id, provider)


@schedule(
    job=discovery_job,
    cron_schedule="0 * * * *",
    execution_timezone="UTC",
    default_status=DefaultScheduleStatus.RUNNING,
)
def discovery_schedule(context: ScheduleEvaluationContext):
    """Hourly: refresh the installed-org roster.

    The per-org ingestion runs are launched by ``org_fanout_sensor`` when this
    job succeeds, so the schedule itself stays a single cheap run. Auto-starts
    so it is live as soon as the daemon boots.
    """
    stamp = context.scheduled_execution_time.strftime("%Y%m%dT%H%M")
    return RunRequest(run_key=f"discovery:{stamp}")


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[discovery_job],
    request_job=org_ingestion_job,
    default_status=DefaultSensorStatus.RUNNING,
)
def org_fanout_sensor(context: RunStatusSensorContext):
    """Fan out one ``org_ingestion_job`` run per installed org.

    Fires on every successful ``discovery_job`` run. Each RunRequest is tagged
    with the org's connected_account id (and login), which the ops read to
    scope their work. The ``run_key`` includes the discovery run id so a
    sensor retry never double-launches an org.
    """
    try:
        accounts = _run(_list_accounts())
    except Exception as exc:  # noqa: BLE001 — surface as a skip, not a crash
        return SkipReason(f"Could not list active orgs: {exc}")

    if not accounts:
        return SkipReason("No active GitHub connected accounts to ingest")

    # Boot the Dask worker fleet now so workers register while the runs queue
    # (Fargate cold start ~1-2 min; Dask holds steps until workers join).
    worker_scaling.scale_up_for_runs(len(accounts))

    discovery_run_id = context.dagster_run.run_id
    return [
        RunRequest(
            run_key=f"{account_id}:{discovery_run_id}",
            tags={_ACCOUNT_TAG: account_id, _ORG_TAG: org or ""},
        )
        for account_id, org in accounts
    ]


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[discovery_job],
    request_job=linear_ingestion_job,
    default_status=DefaultSensorStatus.RUNNING,
)
def linear_fanout_sensor(context: RunStatusSensorContext):
    """Fan out one ``linear_ingestion_job`` run per connected Linear workspace.

    Shares the hourly ``discovery_job`` cadence with ``org_fanout_sensor``.
    Linear workspaces are provisioned by the OAuth connect flow (no external
    installation sync), so this just lists the active Linear accounts and tags
    each run with its connected_account id.
    """
    try:
        accounts = _run(_list_accounts(provider="linear"))
    except Exception as exc:  # noqa: BLE001 — surface as a skip, not a crash
        return SkipReason(f"Could not list active Linear workspaces: {exc}")

    if not accounts:
        return SkipReason("No active Linear connected accounts to ingest")

    worker_scaling.scale_up_for_runs(len(accounts))

    discovery_run_id = context.dagster_run.run_id
    return [
        RunRequest(
            run_key=f"linear:{account_id}:{discovery_run_id}",
            tags={_ACCOUNT_TAG: account_id, _ORG_TAG: name or ""},
        )
        for account_id, name in accounts
    ]


# Runs that need Dask workers: anything queued or in progress for the org or
# Linear ingestion jobs. CANCELING still holds workers (steps may be mid-flight).
_ACTIVE_RUN_STATUSES = [
    DagsterRunStatus.QUEUED,
    DagsterRunStatus.NOT_STARTED,
    DagsterRunStatus.STARTING,
    DagsterRunStatus.STARTED,
    DagsterRunStatus.CANCELING,
]


@sensor(
    job=org_ingestion_job,
    minimum_interval_seconds=60,
    default_status=DefaultSensorStatus.RUNNING,
    description=(
        "Reconcile the Dask worker ECS service against active ingestion runs: "
        "scale up for queued/running org runs (incl. manual launches), scale "
        "to zero when idle. Requests no runs itself."
    ),
)
def dask_worker_scaling_sensor(context: SensorEvaluationContext):
    """Keep the worker fleet sized to the actual run queue (0 when idle)."""
    if not worker_scaling.scaling_enabled():
        return SkipReason("Dask worker autoscaling disabled (no ECS service env)")

    active = sum(
        context.instance.get_runs_count(
            RunsFilter(job_name=job_name, statuses=_ACTIVE_RUN_STATUSES)
        )
        for job_name in ("org_ingestion_job", "linear_ingestion_job")
    )
    try:
        summary = worker_scaling.reconcile(active)
    except Exception as exc:  # noqa: BLE001 — surface as a skip, not a crash
        return SkipReason(f"Dask worker fleet reconcile failed: {exc}")
    return SkipReason(f"Dask worker fleet: {summary}")
