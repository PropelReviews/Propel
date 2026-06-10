"""Dagster-driven autoscaling for the Dask worker fleet on ECS.

The stack deliberately has no CloudWatch (see infrastructure/terraform/README),
so instead of Application Auto Scaling the Dagster coordinator scales the
worker ECS service directly — it is the component that knows, exactly and
immediately, how many ingestion runs are queued:

- ``org_fanout_sensor`` scales up to ``min(orgs, DASK_WORKER_MAX)`` the moment
  it fans out the hourly runs (workers boot while the runs queue).
- ``dask_worker_scaling_sensor`` reconciles every minute: it scales up for
  manually launched runs and scales the fleet to **zero** once no
  ``org_ingestion_job`` run is queued or in progress. It never scales down
  while runs are active — ECS picks scale-in victims arbitrarily and would
  kill workers mid-step.

Scaling is a no-op unless ``DASK_WORKER_ECS_CLUSTER`` and
``DASK_WORKER_ECS_SERVICE`` are set (they are injected by Terraform on the
coordinator task only), so local dev and tests never touch AWS. Terraform
declares the worker service with ``desired_count = 0`` and ignores drift on
it, so applies never fight the scaler.

Fargate cold start is ~1-2 minutes; Dask holds submitted steps until a worker
registers, so early steps wait instead of failing.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("propel.ingestion.dask_scaling")

CLUSTER_ENV = "DASK_WORKER_ECS_CLUSTER"
SERVICE_ENV = "DASK_WORKER_ECS_SERVICE"
MAX_WORKERS_ENV = "DASK_WORKER_MAX"

_DEFAULT_MAX_WORKERS = 4


def scaling_enabled() -> bool:
    return bool(os.environ.get(CLUSTER_ENV) and os.environ.get(SERVICE_ENV))


def max_workers() -> int:
    raw = os.environ.get(MAX_WORKERS_ENV, "")
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MAX_WORKERS


def _ecs_client():
    import boto3  # provided by dagster-aws; only imported when scaling is on

    return boto3.client("ecs")


def current_desired_count() -> int:
    response = _ecs_client().describe_services(
        cluster=os.environ[CLUSTER_ENV],
        services=[os.environ[SERVICE_ENV]],
    )
    services = response.get("services") or []
    if not services:
        raise RuntimeError(f"ECS service {os.environ[SERVICE_ENV]} not found")
    return int(services[0]["desiredCount"])


def set_desired_count(count: int) -> None:
    _ecs_client().update_service(
        cluster=os.environ[CLUSTER_ENV],
        service=os.environ[SERVICE_ENV],
        desiredCount=count,
    )
    logger.info(
        "Dask worker fleet scaled",
        extra={
            "event": "dask.scale",
            "dask.desired_count": count,
            "dask.service": os.environ[SERVICE_ENV],
        },
    )


def scale_up_for_runs(active_runs: int) -> None:
    """Best-effort scale-up to cover ``active_runs`` (never scales down)."""
    if not scaling_enabled() or active_runs <= 0:
        return
    try:
        target = min(active_runs, max_workers())
        if current_desired_count() < target:
            set_desired_count(target)
    except Exception:  # noqa: BLE001 — scaling must never break run launching
        logger.exception("Dask worker scale-up failed")


def reconcile(active_runs: int) -> str:
    """Reconcile the fleet against the active run count; returns a summary."""
    current = current_desired_count()
    if active_runs > 0:
        target = min(active_runs, max_workers())
        if target > current:
            set_desired_count(target)
            return f"scaled up {current} -> {target} ({active_runs} active runs)"
        return f"no change ({current} workers, {active_runs} active runs)"
    if current > 0:
        set_desired_count(0)
        return f"scaled down {current} -> 0 (no active runs)"
    return "idle (0 workers, 0 active runs)"
