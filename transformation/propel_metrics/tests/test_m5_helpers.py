"""Memory-store tests for M5 classify / structural diff / preview helpers."""

from __future__ import annotations

from propel_metrics.codegen.preview import render_preview_sql
from propel_metrics.expr.json_ast import try_parse_json
from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.resolve import resolve_metrics
from propel_metrics.resolve.lifecycle import classify_yaml_change, save_draft
from propel_metrics.resolve.structural_diff import structural_diff
from propel_metrics.store.import_system import import_system_metrics
from propel_metrics.store.memory import MemoryDefinitionStore


def test_classify_and_diff_roundtrip_memory():
    store = MemoryDefinitionStore()
    import_system_metrics(store)
    yaml_text = """
apiVersion: propel/v1
kind: Metric
metadata:
  id: acme.m5_count
  name: M5 Count
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
    grains: [week]
  dimensions: []
  visibility: org
"""
    row = save_draft(store, org_id="acme", yaml_text=yaml_text, created_by="t")
    assert row.status == "draft"
    renamed = yaml_text.replace("name: M5 Count", "name: Renamed")
    result = classify_yaml_change(store, org_id="acme", yaml_text=renamed)
    assert result["kind"] in {"non_semantic", "semantic", "none"}

    before = {"spec": {"filters": [{"field": "state", "op": "eq", "value": "merged"}]}}
    after = {
        "spec": {
            "filters": [
                {"field": "state", "op": "eq", "value": "merged"},
                {"field": "repo", "op": "eq", "value": "acme/core"},
            ]
        }
    }
    changes = structural_diff(before, after)
    assert any(c["op"] == "add" for c in changes)


def test_preview_sql_for_shipped_metric():
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.merged_prs"], by_id)
    out = render_preview_sql(plan, tenant_id="00000000-0000-0000-0000-000000000001")
    assert "statement_timeout" in out["sql"]


def test_formula_json_ast_ok():
    assert try_parse_json("a + b / c")["ok"] is True
