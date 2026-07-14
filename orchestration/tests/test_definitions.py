"""Guardrails for the Dagster code location.

The ECS coordinator runs ``dagster api grpc -m propel_orchestration.definitions``.
If ``Definitions.get_repository_def()`` raises (e.g. conflicting AssetSpecs),
that process exits and the webserver surfaces:

    DagsterUserCodeUnreachableError: Could not reach user code server
    gRPC UNAVAILABLE / connection refused on :4000

Importing job modules alone does not catch this — repository construction does.
"""

from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path

import pytest


@pytest.fixture(scope="module", autouse=True)
def _ensure_dbt_manifest() -> None:
    """analytics.py needs a parsed manifest when not under ``dagster dev``."""
    project = Path(__file__).resolve().parents[2] / "transformation" / "dbt"
    manifest = project / "target" / "manifest.json"
    if manifest.exists():
        return
    env = {
        **os.environ,
        "DBT_HOST": os.environ.get("DBT_HOST", "localhost"),
        "DBT_PORT": os.environ.get("DBT_PORT", "5432"),
        "DBT_USER": os.environ.get("DBT_USER", "propel"),
        "DBT_PASSWORD": os.environ.get("DBT_PASSWORD", "propel"),
        "DBT_DBNAME": os.environ.get("DBT_DBNAME", "propel"),
    }
    subprocess.run(
        ["dbt", "parse", "--project-dir", str(project), "--profiles-dir", str(project)],
        check=True,
        env=env,
    )


def test_ingestion_asset_specs_have_unique_keys() -> None:
    """Duplicate AssetSpec keys crash Definitions resolution (Dagster >=1.11)."""
    from propel_orchestration.analytics import ingestion_asset_specs

    keys = [spec.key for spec in ingestion_asset_specs]
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    assert not duplicates, f"duplicate ingestion AssetSpec keys: {duplicates}"


def test_definitions_repository_loads() -> None:
    """Full code-location load — same path the gRPC server uses at boot."""
    from propel_orchestration.definitions import defs

    repo = defs.get_repository_def()
    asset_keys = list(repo.asset_graph.get_all_asset_keys())
    assert asset_keys, "expected at least one asset in the repository"

    # Spot-check lineage anchors that previous duplicate-spec bugs hit.
    key_strs = {str(k) for k in asset_keys}
    assert any("reviews" in s for s in key_strs)
    assert any("fct_metric_values" in s or "metric_propel" in s for s in key_strs)

    job_names = {j.name for j in repo.get_all_jobs()}
    assert "metrics_compile_build" in job_names

    # Sensor is registered on the Definitions object (not only the job).
    from propel_orchestration.definitions import defs as definitions

    sensor_names = {s.name for s in definitions.sensors}
    assert "metrics_compile_dirty_sensor" in sensor_names
