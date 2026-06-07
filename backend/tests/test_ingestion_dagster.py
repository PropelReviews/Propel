"""Tests for Dagster ingestion definitions."""

from app.ingestion.dagster.definitions import defs, ingestion_job, org_ingestion_dag


def test_ingestion_job_loads():
    assert ingestion_job.name == "ingestion_job"


def test_definitions_has_hourly_schedule():
    assert defs.get_schedule_def("hourly_ingestion_schedule") is not None


def test_org_subgraph_ops_are_chained():
    node_names = {node.name for node in org_ingestion_dag.nodes}
    assert {
        "github_sync",
        "github_org_sync",
        "github_user_profiles_sync",
        "copilot_sync",
    }.issubset(node_names)


def test_ingestion_job_wires_discovery_to_subgraph():
    node_names = {node.name for node in ingestion_job.graph.nodes}
    assert node_names == {"discover_active_accounts", "org_ingestion_dag"}
