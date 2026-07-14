"""M4 exit-criteria harness (in-memory store)."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml
from propel_metrics.codegen.shared import compile_org_results
from propel_metrics.resolve.lifecycle import activate, repin, save_draft
from propel_metrics.resolve.org import resolve_org
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import METRIC_SET_ID
from propel_metrics.sync.pushpull import pull, push


def _set(org: str, enabled: list[str], params: dict | None = None):
    standard: dict = {"mode": "explicit", "enabled": enabled}
    if params:
        standard["params"] = params
    return {
        "apiVersion": "propel/v1",
        "kind": "MetricSet",
        "metadata": {"org": org},
        "spec": {"standard": standard, "custom": []},
    }


def test_m4_exit_criteria(tmp_path: Path) -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)

    # Patch deployment_frequency with a bindable param for override demo
    row = store.get_definition(
        "__system", "propel.deployment_frequency", status="active"
    )
    assert row is not None
    doc = copy.deepcopy(row.doc)
    doc["spec"]["params"] = {
        "include_prereleases": {
            "type": "boolean",
            "default": False,
            "binds": {"filter": {"field": "is_prerelease", "op": "eq"}},
        }
    }
    store.put_metric_doc(
        "__system",
        doc,
        yaml_text=yaml.safe_dump(doc),
        status="active",
        version=row.version,
    )

    # 1) Two orgs, disjoint sets
    store.put_metric_doc(
        "acme",
        _set(
            "acme",
            ["propel.merged_prs", "propel.deployment_frequency"],
            params={"propel.deployment_frequency": {"include_prereleases": True}},
        ),
        status="active",
    )
    store.put_metric_doc(
        "beta",
        _set("beta", ["propel.merged_prs", "propel.cycle_time"]),
        status="active",
    )

    # Custom ratio + mapping on acme
    store.put_metric_doc(
        "acme",
        {
            "apiVersion": "propel/v1",
            "kind": "DimensionMapping",
            "metadata": {"id": "acme.author_to_team"},
            "spec": {
                "entity": "pull_request",
                "from_field": "author_id",
                "to_dimension": "team",
                "default": "other",
                "mapping": {"alice": "platform"},
            },
        },
        status="active",
    )
    custom = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {
            "id": "acme.team_revert_rate",
            "name": "Team revert rate",
            "status": "active",
            "version": 1,
        },
        "spec": {
            "measure": {
                "type": "ratio",
                "numerator": {"ref": "propel.reverted_prs"},
                "denominator": {"ref": "propel.merged_prs"},
                "zero_denominator": None,
            },
            "time": {"grains": ["week"]},
            "dimensions": ["team"],
            "visibility": "org",
        },
    }
    store.put_metric_doc("acme", custom, status="active")
    # Add custom to metric set
    ms = store.get_definition("acme", METRIC_SET_ID, status="active")
    assert ms is not None
    ms_doc = copy.deepcopy(ms.doc)
    ms_doc["spec"]["custom"] = ["acme.team_revert_rate"]
    store.put_metric_doc("acme", ms_doc, status="active", version=ms.version)

    acme = resolve_org(store, "acme")
    beta = resolve_org(store, "beta")
    acme_ids = {m.metric_id for m in acme.metrics}
    beta_ids = {m.metric_id for m in beta.metrics}
    assert acme_ids != beta_ids
    assert "propel.cycle_time" in beta_ids
    assert "propel.cycle_time" not in acme_ids

    # 2) Shared standard (merged_prs) same hash
    a_mp = next(m for m in acme.metrics if m.metric_id == "propel.merged_prs")
    b_mp = next(m for m in beta.metrics if m.metric_id == "propel.merged_prs")
    assert a_mp.content_hash == b_mp.content_hash

    # 3) Param override differs
    a_df = next(m for m in acme.metrics if m.metric_id == "propel.deployment_frequency")
    # beta doesn't enroll DF — compare against a default resolve
    store.put_metric_doc(
        "gamma",
        _set("gamma", ["propel.deployment_frequency"]),
        status="active",
    )
    gamma = resolve_org(store, "gamma")
    g_df = next(
        m for m in gamma.metrics if m.metric_id == "propel.deployment_frequency"
    )
    assert a_df.content_hash != g_df.content_hash

    # 4) Mapped team ratio
    ratio = next(m for m in acme.metrics if m.metric_id == "acme.team_revert_rate")
    assert ratio.plan.dimensions == ("team",)
    assert ratio.plan.aggregations["num"].operand.mapped_dimensions

    written = compile_org_results([acme, beta, gamma], output_dir=tmp_path / "gen")
    assert any("merged_prs" in p.name for p in written)
    assert (tmp_path / "gen" / "metric_enrollment.sql").is_file()

    # 5) push → conflict → pull → push
    out = tmp_path / "sync"
    pull(store, org_id="acme", directory=out)
    # bump server-side metric set
    bumped = copy.deepcopy(ms_doc)
    bumped["spec"]["standard"]["enabled"].append("propel.reverted_prs")
    save_draft(store, org_id="acme", yaml_text=yaml.safe_dump(bumped), created_by="x")
    activate(store, org_id="acme", metric_id=METRIC_SET_ID)
    conflicted = push(store, org_id="acme", directory=out, atomic=True)
    assert conflicted.conflicts
    pull(store, org_id="acme", directory=out)
    ok = push(store, org_id="acme", directory=out, atomic=True)
    assert ok.conflicts == []

    # 6) repin after propel.* bump
    child = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {
            "id": "acme.cycle_child",
            "name": "Child",
            "status": "draft",
            "version": 1,
        },
        "spec": {
            "extends": "propel.cycle_time",
            "overrides": {"display": {"unit": "duration"}},
        },
    }
    store.put_metric_doc(
        "acme",
        child,
        status="draft",
        parent_pin={"metric_id": "propel.cycle_time", "version": 1},
    )
    activate(store, org_id="acme", metric_id="acme.cycle_child", version=1)

    parent = store.get_definition("__system", "propel.cycle_time", status="active")
    assert parent is not None
    parent_doc = copy.deepcopy(parent.doc)
    parent_doc["metadata"]["version"] = parent.version + 1
    parent_doc["spec"] = copy.deepcopy(parent.doc["spec"])
    parent_doc["spec"]["filters"] = list(parent_doc["spec"].get("filters") or [])
    parent_doc["spec"]["filters"].append(
        {"field": "state", "op": "eq", "value": "merged"}
    )
    store.put_metric_doc(
        "__system",
        parent_doc,
        yaml_text=yaml.safe_dump(parent_doc),
        status="draft",
        version=parent.version + 1,
    )
    activate(
        store,
        org_id="__system",
        metric_id="propel.cycle_time",
        version=parent.version + 1,
        known_orgs=["acme"],
    )
    assert any(
        n.notice == "parent_version_available"
        for n in store.list_notices("acme", "acme.cycle_child")
    )
    repinned = repin(store, org_id="acme", metric_id="acme.cycle_child")
    assert repinned.parent_pin["version"] == parent.version + 1
