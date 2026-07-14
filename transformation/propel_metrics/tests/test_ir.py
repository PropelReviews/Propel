"""IR build + golden SQL smoke tests."""

from __future__ import annotations

import re

from propel_metrics.codegen.sql import render_plan_sql
from propel_metrics.ir import MappedDim, build_compiled_plan, plan_content_hash
from propel_metrics.ir.hashutil import plan_canonical_json
from propel_metrics.resolve import ResolvedMetric, resolve_metrics


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def test_build_simple_plan() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.merged_prs"], by_id)
    assert plan.kind == "simple"
    assert "value" in plan.aggregations
    assert plan.aggregations["value"].agg.method == "count"
    assert plan.grains == ("day", "week", "month")
    assert "propel.merged_prs" in plan_canonical_json(plan)
    digest = plan_content_hash(plan)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_golden_merged_prs_contains_rows_cte() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.merged_prs"], by_id)
    sql = render_plan_sql(plan, source="merged_prs.yaml")
    n = _norm(sql)
    assert "m_rows as" in n
    assert "grain_day as" in n
    assert "materialized='table'" in n
    assert "dim_team" in n


def test_golden_window_metric_refs_spine() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.cycle_time_trailing_30d"], by_id)
    assert plan.windows[0].days == 30
    assert plan.grains == ()
    sql = render_plan_sql(plan, source="cycle_time_trailing_30d.yaml")
    assert "ref('dim_step_spine')" in sql
    assert "rolling_30d" in sql
    assert "win_30d_day" in sql


def test_mapped_team_dimension_emits_case() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    metric = by_id["propel.merged_prs"]
    spec = dict(metric.spec)
    spec["dimensions"] = ["repo", "team"]
    patched = ResolvedMetric(
        metric_id=metric.metric_id,
        name=metric.name,
        status=metric.status,
        version=metric.version,
        definition_version=metric.definition_version,
        spec=spec,
        source_path=metric.source_path,
    )
    mapped = MappedDim(
        name="team",
        from_field="author_id",
        default="other",
        mapping=(("alice", "platform"), ("bob", "growth")),
    )
    plan = build_compiled_plan(patched, by_id, mapped_dimensions={"team": mapped})
    assert plan.dimensions == ("repo", "team")
    assert plan.aggregations["value"].operand.mapped_dimensions[0].name == "team"
    sql = render_plan_sql(plan, source="test")
    assert "case base.author_id" in sql
    assert "when 'alice' then 'platform'" in sql
    assert "as dim_team" in sql
    assert "dim_repo" in sql
    assert "mapped_dimensions" in plan_canonical_json(plan)
