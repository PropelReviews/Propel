"""Resolve + codegen tests."""

from __future__ import annotations

from propel_metrics.codegen import compile_metrics
from propel_metrics.codegen.sql import is_compilable, render_metric_sql
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


def test_ratio_not_compilable_in_m2() -> None:
    resolved = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    assert not is_compilable(resolved["propel.change_failure_rate"])


def test_render_cycle_time_sql_contains_percentile() -> None:
    metric = next(
        m
        for m in resolve_metrics(active_only=True)
        if m.metric_id == "propel.cycle_time"
    )
    sql = render_metric_sql(metric)
    assert "ref('pull_request')" in sql
    assert "percentile_cont(0.5)" in sql
    assert "propel.cycle_time" in sql


def test_compile_writes_generated_files(tmp_path) -> None:
    written = compile_metrics(output_dir=tmp_path)
    names = {p.name for p in written}
    assert "fct_metric_values.sql" in names
    assert "metric_propel_cycle_time.sql" in names
    assert "metric_propel_deployment_frequency.sql" in names
    assert "schema.yml" in names
    # ratio skipped
    assert "metric_propel_change_failure_rate.sql" not in names
