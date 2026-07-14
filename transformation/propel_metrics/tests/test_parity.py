"""File vs store resolve parity tests."""

from __future__ import annotations

from propel_metrics.resolve.parity import file_pipeline_hashes, resolve_parity
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import METRIC_SET_ID


def test_resolve_parity_default_on_matches_file_pipeline() -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    # Implicit MetricSet (default_on, no params) — resolve_org synthesizes it
    mismatches = resolve_parity(store, "parityorg")
    assert mismatches == [], mismatches


def test_resolve_parity_ignores_param_overrides() -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    # Patch DF with a param and override it — should not count as mismatch
    row = store.get_definition(
        "__system", "propel.deployment_frequency", status="active"
    )
    assert row is not None
    import copy

    import yaml

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
    store.put_metric_doc(
        "acme",
        {
            "apiVersion": "propel/v1",
            "kind": "MetricSet",
            "metadata": {"org": "acme"},
            "spec": {
                "standard": {
                    "mode": "explicit",
                    "enabled": ["propel.deployment_frequency"],
                    "params": {
                        "propel.deployment_frequency": {"include_prereleases": True}
                    },
                }
            },
        },
        status="active",
    )
    store.set_status("acme", METRIC_SET_ID, 1, "active")
    mismatches = resolve_parity(store, "acme")
    # Param-overridden DF skipped; no other enrolled standards → empty
    assert mismatches == []
    assert "propel.deployment_frequency" in file_pipeline_hashes()
