"""Resolve + codegen tests."""

from __future__ import annotations

from propel_metrics.codegen import compile_metrics
from propel_metrics.codegen.sql import is_compilable, render_metric_sql
from propel_metrics.ir import build_compiled_plan
from propel_metrics.resolve import resolve_metrics


def test_extends_merges_percentile() -> None:
    resolved = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    assert "propel.cycle_time_p90" in resolved
    child = resolved["propel.cycle_time_p90"]
    assert child.spec["measure"]["type"] == "interval"
    assert child.spec["measure"]["agg"] == "percentile"
    assert child.spec["measure"]["percentile"] == 90
    assert child.spec["entity"] == "pull_request"
    assert child.spec["time"]["field"] == "merged_at"


def test_ratio_compilable_in_m3() -> None:
    resolved = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    assert is_compilable(resolved["propel.change_failure_rate"])


def test_trailing_window_compilable() -> None:
    resolved = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    metric = resolved["propel.cycle_time_trailing_30d"]
    assert is_compilable(metric)
    assert metric.spec["time"].get("grains") == []
    assert metric.spec["time"]["windows"][0]["days"] == 30


def test_render_cycle_time_sql_contains_percentile() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    metric = by_id["propel.cycle_time"]
    sql = render_metric_sql(metric, by_id=by_id)
    assert "ref('pull_request')" in sql
    assert "percentile_cont(0.5)" in sql
    assert "propel.cycle_time" in sql
    assert "materialized='table'" in sql
    assert "m_rows as" in sql


def test_render_cfr_ratio_sql() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    metric = by_id["propel.change_failure_rate"]
    plan = build_compiled_plan(metric, by_id)
    assert plan.kind == "ratio"
    sql = render_metric_sql(metric, by_id=by_id)
    assert "num_rows as" in sql
    assert "den_rows as" in sql
    assert "nullif(den.v, 0)" in sql
    assert "numerator" in sql


def test_compile_writes_generated_files(tmp_path) -> None:
    written = compile_metrics(output_dir=tmp_path)
    names = {p.name for p in written}
    assert "fct_metric_values.sql" in names
    assert "metric_propel_cycle_time.sql" in names
    assert "metric_propel_deployment_frequency.sql" in names
    assert "metric_propel_change_failure_rate.sql" in names
    assert "metric_propel_cycle_time_trailing_30d.sql" in names
    assert "schema.yml" in names
    fct = (tmp_path / "fct_metric_values.sql").read_text(encoding="utf-8")
    assert "materialized='table'" in fct
