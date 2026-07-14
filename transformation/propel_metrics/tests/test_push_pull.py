"""push/pull + lifecycle tests."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml
from propel_metrics.resolve.lifecycle import activate, repin, save_draft
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import METRIC_SET_ID
from propel_metrics.sync.pushpull import pull, push


def _metric_set(org: str):
    return {
        "apiVersion": "propel/v1",
        "kind": "MetricSet",
        "metadata": {"org": org},
        "spec": {
            "standard": {
                "mode": "explicit",
                "enabled": ["propel.merged_prs"],
            }
        },
    }


def test_pull_noop_push(tmp_path: Path) -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    store.put_metric_doc("acme", _metric_set("acme"), status="active")
    out = tmp_path / "out"
    pull(store, org_id="acme", directory=out)
    result = push(store, org_id="acme", directory=out)
    assert result.conflicts == []
    assert result.drafted == []
    assert result.created == []
    assert "propel.merged_prs" in result.unchanged or result.unchanged


def test_semantic_edit_creates_draft_version(tmp_path: Path) -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    store.put_metric_doc("acme", _metric_set("acme"), status="active")
    out = tmp_path / "out"
    pull(store, org_id="acme", directory=out)

    custom = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {
            "id": "acme.extra_merges",
            "name": "Extra",
            "status": "draft",
            "version": 1,
        },
        "spec": {
            "entity": "pull_request",
            "measure": {"type": "count"},
            "filters": [{"field": "state", "op": "eq", "value": "merged"}],
            "time": {"field": "merged_at", "grains": ["day"]},
            "dimensions": [],
            "visibility": "org",
        },
    }
    path = out / "acme" / "extra_merges.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(custom), encoding="utf-8")
    result = push(store, org_id="acme", directory=out, activate_flag=True)
    assert (
        "acme.extra_merges" in result.created or "acme.extra_merges" in result.activated
    )
    active = store.get_definition("acme", "acme.extra_merges", status="active")
    assert active is not None


def test_stale_lock_conflicts(tmp_path: Path) -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    store.put_metric_doc("acme", _metric_set("acme"), status="active")
    out = tmp_path / "out"
    pull(store, org_id="acme", directory=out)

    # Server-side version bump of metric set
    doc = copy.deepcopy(_metric_set("acme"))
    doc["spec"]["standard"]["enabled"] = [
        "propel.merged_prs",
        "propel.deployment_frequency",
    ]
    save_draft(
        store,
        org_id="acme",
        yaml_text=yaml.safe_dump(doc),
        created_by="other",
    )
    activate(store, org_id="acme", metric_id=METRIC_SET_ID)

    # Local stale push of old metric set content
    result = push(store, org_id="acme", directory=out, atomic=True)
    assert METRIC_SET_ID in result.conflicts or result.conflicts


def test_repin_after_parent_bump() -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)

    # Child extending cycle_time
    child = {
        "apiVersion": "propel/v1",
        "kind": "Metric",
        "metadata": {
            "id": "acme.cycle_time_custom",
            "name": "Custom CT",
            "status": "draft",
            "version": 1,
        },
        "spec": {
            "extends": "propel.cycle_time",
            "overrides": {
                "display": {"unit": "duration", "format": "humanize_duration"}
            },
        },
    }
    store.put_metric_doc(
        "acme",
        child,
        status="draft",
        parent_pin={"metric_id": "propel.cycle_time", "version": 1},
    )
    activate(store, org_id="acme", metric_id="acme.cycle_time_custom", version=1)
    child_active = store.get_definition(
        "acme", "acme.cycle_time_custom", status="active"
    )
    assert child_active is not None
    assert child_active.parent_pin == {
        "metric_id": "propel.cycle_time",
        "version": 1,
    }

    # Bump parent version in store
    parent = store.get_definition("__system", "propel.cycle_time", status="active")
    assert parent is not None
    parent_doc = copy.deepcopy(parent.doc)
    parent_doc["metadata"]["version"] = 2
    parent_doc["metadata"]["description"] = "bumped"
    # Force semantic change
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
        version=2,
    )
    activate(
        store,
        org_id="__system",
        metric_id="propel.cycle_time",
        version=2,
        known_orgs=["acme"],
    )
    notices = store.list_notices("acme", "acme.cycle_time_custom")
    assert any(n.notice == "parent_version_available" for n in notices)

    repinned = repin(store, org_id="acme", metric_id="acme.cycle_time_custom")
    assert repinned.parent_pin == {
        "metric_id": "propel.cycle_time",
        "version": 2,
    }
    assert repinned.version >= 2
