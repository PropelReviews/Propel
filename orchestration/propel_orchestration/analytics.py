"""Dagster analytics layer: dbt models as software-defined assets.

The dbt project in ``transformation/dbt`` is loaded with ``dagster-dbt`` so
every model is a first-class Dagster asset — lineage from the ingestion assets
(``github/pull_requests`` …) through ``stg_github_pull_requests`` to
``analytics.fct_pr_activity_daily``, dbt tests as asset checks, materialization
history, and UI backfills.

Analytics runs are **tenant-partitioned** (``DynamicPartitionsDefinition``):
``analytics_sensor`` fires on every successful ``org_ingestion_job`` run,
resolves the org's ``connected_account.tenant_id``, registers the partition if
it is new, and requests a materialization for it. The asset body maps the
partition key onto ``dbt build --vars '{tenant_id: ...}'`` so the incremental
marts only recompute that tenant's rows. Backfilling any subset of tenants is a
native UI operation; a manual full rebuild is ``dbt build --full-refresh`` (see
``transformation/README.md``).

Concurrency: every analytics run carries ``dagster/concurrency_key: dbt`` so
simultaneous per-tenant runs queue (limit configured in ``dagster.yaml``)
instead of racing delete+insert statements on the same target table.

Note: no ``from __future__ import annotations`` in this module — it would turn
the ``context: AssetExecutionContext`` annotation into a string, which
Dagster's context type-hint validation rejects at definition load.
"""

import json
import logging
import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    AssetSpec,
    DagsterRunStatus,
    DefaultSensorStatus,
    DynamicPartitionsDefinition,
    RunRequest,
    RunStatusSensorContext,
    SkipReason,
    define_asset_job,
    run_status_sensor,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

from propel_orchestration.jobs import _ACCOUNT_TAG, _run, linear_ingestion_job, org_ingestion_job

logger = logging.getLogger("propel.analytics.dagster")

_DBT_CONCURRENCY_TAGS = {"dagster/concurrency_key": "dbt"}


def _export_dbt_env() -> None:
    """Derive DBT_* connection env vars from DATABASE_URL.

    profiles.yml reads DBT_HOST/PORT/USER/PASSWORD/DBNAME; the orchestration
    container only carries DATABASE_URL, so translate it here (import time —
    needed for both manifest parsing and `dbt build` runs). Explicitly set
    DBT_* vars always win.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return
    parsed = urlsplit(url.replace("+asyncpg", "").replace("+psycopg", ""))
    derived = {
        "DBT_HOST": parsed.hostname or "",
        "DBT_PORT": str(parsed.port or 5432),
        "DBT_USER": unquote(parsed.username or ""),
        "DBT_PASSWORD": unquote(parsed.password or ""),
        "DBT_DBNAME": parsed.path.lstrip("/"),
    }
    for key, value in derived.items():
        if value:
            os.environ.setdefault(key, value)


def _dbt_project_dir() -> Path:
    """Locate the dbt project: baked/mounted /transformation in containers,
    repo-relative when running from a checkout."""
    candidates = [
        Path("/transformation/dbt"),
        Path(__file__).resolve().parents[2] / "transformation" / "dbt",
    ]
    for candidate in candidates:
        if (candidate / "dbt_project.yml").exists():
            return candidate
    raise FileNotFoundError(
        "dbt project not found (looked in /transformation/dbt and the repo checkout)"
    )


_export_dbt_env()

dbt_project = DbtProject(
    project_dir=_dbt_project_dir(),
    profiles_dir=_dbt_project_dir(),
)
# `dagster dev` re-parses the manifest on each code-location load so model edits
# show up live; prod relies on the manifest baked at image build (`dbt parse`).
dbt_project.prepare_if_dev()
if not dbt_project.manifest_path.exists():
    subprocess.run(
        ["dbt", "parse"],
        cwd=dbt_project.project_dir,
        check=True,
        env={**os.environ, "DBT_PROFILES_DIR": str(dbt_project.project_dir)},
    )

tenant_partitions = DynamicPartitionsDefinition(name="tenant")


@dbt_assets(manifest=dbt_project.manifest_path, partitions_def=tenant_partitions)
def propel_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Build the dbt project, scoped to one tenant when partitioned.

    The tenant partition key becomes ``--vars '{tenant_id: ...}'``; the
    incremental marts then delete+insert only that tenant's rows.
    """
    args = ["build"]
    if context.has_partition_key:
        args += ["--vars", json.dumps({"tenant_id": context.partition_key})]
    yield from dbt.cli(args, context=context).stream()


# The ingestion ops (jobs.py) emit AssetMaterializations for these keys; declare
# them as external asset specs so they render as real upstream nodes and the
# dbt source mapping (models/sources.yml -> github/pull_requests) connects the
# graph end to end.
ingestion_asset_specs = [
    AssetSpec(
        key=["github", "org_members"],
        description="Org member roster synced from GitHub.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "user_profiles"],
        description="Enriched member profiles synced from GitHub.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "commits"],
        description="Commits pulled across the org's repositories.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "pull_requests"],
        description="Pull requests and review comments (raw_record).",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "reviews"],
        description="Pull-request reviews (same Meltano job as pull_requests).",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "issues"],
        description="Issues and issue comments pulled across the org's repos.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "reviews"],
        description="Pull-request reviews landed with the pull_requests job.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "review_comments"],
        description="Pull-request review comments landed with the pull_requests job.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "releases"],
        description="GitHub Releases used for DORA deployment frequency.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "workflow_runs"],
        description="GitHub Actions workflow runs across the org's repos.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["github", "copilot_usage"],
        description="GitHub Copilot usage metrics for the org.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["linear", "issues"],
        description="Issues pulled from the connected Linear workspace.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["linear", "comments"],
        description="Comments pulled from the connected Linear workspace.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["linear", "projects"],
        description="Projects pulled from the connected Linear workspace.",
        group_name="ingestion",
    ),
    AssetSpec(
        key=["linear", "description_edits"],
        description="Issue description-edit history from the Linear workspace.",
        group_name="ingestion",
    ),
]


analytics_assets_job = define_asset_job(
    name="analytics_assets_job",
    selection=AssetSelection.assets(propel_dbt_assets),
    partitions_def=tenant_partitions,
    tags=_DBT_CONCURRENCY_TAGS,
    description="Run the dbt models for one tenant partition.",
)


async def _resolve_tenant_ids(account_id: uuid.UUID | None) -> list[str]:
    """Map a connected account to its tenant id (or list every active tenant).

    Provider-agnostic: GitHub org runs and Linear workspace runs both resolve
    to the owning tenant via connected_accounts.
    """
    from sqlalchemy import select

    from app.db.session import async_session_maker
    from app.models.connected_account import ConnectedAccount
    from app.models.enums import ConnectionStatus

    query = select(ConnectedAccount.tenant_id).where(
        ConnectedAccount.status == ConnectionStatus.active.value,
    )
    if account_id is not None:
        query = query.where(ConnectedAccount.id == account_id)
    async with async_session_maker() as session:
        result = await session.execute(query)
    return sorted({str(tenant_id) for tenant_id in result.scalars().all()})


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    monitored_jobs=[org_ingestion_job, linear_ingestion_job],
    request_job=analytics_assets_job,
    default_status=DefaultSensorStatus.RUNNING,
)
def analytics_sensor(context: RunStatusSensorContext):
    """Recompute a tenant's analytics whenever its raw ingestion succeeds.

    Reads the finished run's account tag, resolves the owning tenant, registers
    the tenant partition if new, and requests exactly one analytics run
    (``run_key`` ties it to the ingestion run id). Untagged ingestion runs
    (manual "all orgs") fan out one analytics run per active tenant.
    """
    account_raw = context.dagster_run.tags.get(_ACCOUNT_TAG)
    account_id = uuid.UUID(account_raw) if account_raw else None

    try:
        tenant_ids = _run(_resolve_tenant_ids(account_id))
    except Exception as exc:  # noqa: BLE001 — surface as a skip, not a crash
        return SkipReason(f"Could not resolve tenant for analytics run: {exc}")

    if not tenant_ids:
        return SkipReason(
            f"No active tenant found for ingestion run {context.dagster_run.run_id}"
        )

    context.instance.add_dynamic_partitions(tenant_partitions.name, tenant_ids)

    ingestion_run_id = context.dagster_run.run_id
    return [
        RunRequest(
            run_key=f"{ingestion_run_id}:{tenant_id}",
            partition_key=tenant_id,
            tags=_DBT_CONCURRENCY_TAGS,
        )
        for tenant_id in tenant_ids
    ]
