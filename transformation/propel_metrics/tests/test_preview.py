"""Tests for preview SQL wrapping + ref rewrite."""

from __future__ import annotations

from propel_metrics.codegen.preview import (
    coarsest_grain,
    plan_for_preview,
    render_preview_sql,
    rewrite_refs,
)
from propel_metrics.ir.build import build_compiled_plan
from propel_metrics.resolve import resolve_metrics


def _merged_prs_plan():
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    return build_compiled_plan(by_id["propel.merged_prs"], by_id)


def test_coarsest_grain():
    assert coarsest_grain(("day", "week", "month")) == "month"


def test_plan_for_preview_drops_windows_and_fine_grains():
    original = _merged_prs_plan()
    plan = plan_for_preview(original)
    assert len(plan.grains) == 1
    assert plan.grains[0] == coarsest_grain(original.grains)
    assert plan.windows == ()


def test_rewrite_refs():
    sql = "from {{ ref('pull_request') }} as base"
    assert rewrite_refs(sql, schema="public") == "from public.pull_request as base"


def test_render_preview_sql_executable_shape():
    result = render_preview_sql(
        _merged_prs_plan(),
        tenant_id="00000000-0000-0000-0000-000000000001",
        relation_schema="public",
    )
    assert "public.pull_request" in result["sql"]
    assert "{{ ref(" not in result["sql"]
    assert "LIMIT 500" in result["sql"]
    assert "SET LOCAL" not in result["sql"]  # set separately by the service
    assert result["diagnostics_sql"] is not None
    assert "count(*)" in result["diagnostics_sql"]
    assert result["grain"] == "month"
