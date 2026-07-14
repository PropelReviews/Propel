"""Lifecycle draft autosave / classify (M5.2)."""

from __future__ import annotations

from propel_metrics.resolve.lifecycle import (
    DraftConflictError,
    classify_yaml_change,
    save_draft,
)
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore


def _count_yaml(org: str, name: str = "sample", extra: str = "") -> str:
    return f"""
apiVersion: propel/v1
kind: Metric
metadata:
  id: {org}.{name}
  name: Sample{extra}
  status: draft
  version: 1
spec:
  entity: pull_request
  measure:
    type: count
  filters:
    - field: state
      op: eq
      value: merged
  time:
    field: merged_at
    grains: [day]
  dimensions: []
  visibility: org
"""


def test_save_draft_updates_open_draft_in_place():
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    row1 = save_draft(
        store, org_id="acme", yaml_text=_count_yaml("acme"), created_by="u1"
    )
    assert row1.version == 1
    assert row1.status == "draft"
    row2 = save_draft(
        store,
        org_id="acme",
        yaml_text=_count_yaml("acme", extra=" Updated"),
        created_by="u1",
    )
    assert row2.version == 1
    assert row2.revision == row1.revision + 1
    drafts = [
        r
        for r in store.list_definitions("acme", kind="Metric", status="draft")
        if r.metric_id == "acme.sample"
    ]
    assert len(drafts) == 1


def test_save_draft_conflict_on_expected_revision():
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    row = save_draft(
        store, org_id="acme", yaml_text=_count_yaml("acme"), created_by="u1"
    )
    try:
        save_draft(
            store,
            org_id="acme",
            yaml_text=_count_yaml("acme", extra=" x"),
            created_by="u2",
            expected_version=row.version,
            expected_revision=row.revision - 1 if row.revision > 0 else 0,
        )
        raised = False
    except DraftConflictError:
        raised = True
    assert raised


def test_classify_yaml_change_semantic_vs_display():
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    base = _count_yaml("acme")
    save_draft(store, org_id="acme", yaml_text=base, created_by="u1")
    from propel_metrics.resolve.lifecycle import activate

    activate(store, org_id="acme", metric_id="acme.sample")

    display_only = base.replace("name: Sample", "name: Renamed")
    result = classify_yaml_change(store, org_id="acme", yaml_text=display_only)
    assert result["kind"] == "non_semantic"

    semantic = base.replace("value: merged", "value: closed")
    result2 = classify_yaml_change(store, org_id="acme", yaml_text=semantic)
    assert result2["kind"] == "semantic"
    assert result2["next_version"] == 2
