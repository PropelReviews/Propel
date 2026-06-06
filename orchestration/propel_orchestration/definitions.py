"""Dagster code location: ingestion job chain + dbt analytics assets.

Imported by the webserver and the daemon (see workspace.yaml). Logging is
configured at import time so both processes ship logs to PostHog as
``propel-ingestion``.

Pipeline: hourly ``discovery_schedule`` -> ``discovery_job`` (get installed
orgs) -> ``org_fanout_sensor`` launches one ``org_ingestion_job`` per org ->
``analytics_sensor`` fires a tenant-partitioned dbt run per finished org.
"""

from __future__ import annotations

from dagster import Definitions
from dagster_dbt import DbtCliResource

from propel_orchestration.analytics import (
    analytics_assets_job,
    analytics_sensor,
    dbt_project,
    ingestion_asset_specs,
    propel_dbt_assets,
)
from propel_orchestration.dask_resource import DaskClusterResource
from propel_orchestration.jobs import (
    dask_worker_scaling_sensor,
    discovery_job,
    discovery_schedule,
    linear_fanout_sensor,
    linear_ingestion_job,
    org_fanout_sensor,
    org_ingestion_job,
)
from propel_orchestration.logging import configure_logging

configure_logging()

defs = Definitions(
    assets=[*ingestion_asset_specs, propel_dbt_assets],
    jobs=[
        discovery_job,
        org_ingestion_job,
        linear_ingestion_job,
        analytics_assets_job,
    ],
    schedules=[discovery_schedule],
    sensors=[
        org_fanout_sensor,
        linear_fanout_sensor,
        analytics_sensor,
        dask_worker_scaling_sensor,
    ],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project),
        # Raw distributed.Client for ops that want in-op parallelism on the
        # shared cluster (the step-level dask_executor is wired in jobs.py).
        "dask": DaskClusterResource(),
    },
)
