"""Shared-model compile tests."""

from __future__ import annotations

from propel_metrics.codegen.shared import compile_org_results, shared_model_filename
from propel_metrics.resolve.org import resolve_org
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore
from propel_metrics.store.protocol import METRIC_SET_ID


def test_shared_compile_dedupes_identical_hashes(tmp_path) -> None:
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    for org in ("acme", "beta"):
        store.put_metric_doc(
            org,
            {
                "apiVersion": "propel/v1",
                "kind": "MetricSet",
                "metadata": {"org": org},
                "spec": {
                    "standard": {
                        "mode": "explicit",
                        "enabled": ["propel.merged_prs"],
                    }
                },
            },
            status="active",
        )
        store.set_status(org, METRIC_SET_ID, 1, "active")

    results = [resolve_org(store, "acme"), resolve_org(store, "beta")]
    hashes = {
        m.content_hash
        for r in results
        for m in r.metrics
        if m.metric_id == "propel.merged_prs"
    }
    assert len(hashes) == 1
    written = compile_org_results(results, output_dir=tmp_path)
    names = {p.name for p in written}
    digest = next(iter(hashes))
    assert shared_model_filename(digest, "propel.merged_prs") in names
    assert "metric_enrollment.sql" in names
