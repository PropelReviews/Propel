"""Property-style tests for ratio ≡ formula and window labeling."""

from __future__ import annotations

from pathlib import Path

import yaml
from propel_metrics.codegen.sql import render_plan_sql
from propel_metrics.expr import emit_sql, parse_expression
from propel_metrics.ir import build_compiled_plan
from propel_metrics.resolve import ResolvedMetric, content_hash


def _metric(
    metric_id: str,
    spec: dict,
    *,
    path: str = "x.yaml",
) -> ResolvedMetric:
    return ResolvedMetric(
        metric_id=metric_id,
        name=metric_id,
        status="active",
        version=1,
        definition_version=content_hash(spec),
        spec=spec,
        source_path=Path(path),
    )


def test_ratio_sql_matches_formula_divide_shape() -> None:
    base = {
        "entity": "pull_request",
        "measure": {"type": "count"},
        "filters": [{"field": "merged_at", "op": "is_not_null"}],
        "time": {"field": "merged_at", "grains": ["day"]},
        "dimensions": [],
    }
    num = _metric(
        "propel.n",
        {
            **base,
            "filters": base["filters"]
            + [{"field": "is_revert", "op": "eq", "value": True}],
        },
    )
    den = _metric("propel.d", base)
    ratio = _metric(
        "propel.r",
        {
            "measure": {
                "type": "ratio",
                "numerator": {"ref": "propel.n"},
                "denominator": {"ref": "propel.d"},
                "zero_denominator": None,
            },
            "time": {"grains": ["day"]},
            "dimensions": [],
        },
    )
    formula = _metric(
        "propel.f",
        {
            "measure": {
                "type": "formula",
                "inputs": {"n": {"ref": "propel.n"}, "d": {"ref": "propel.d"}},
                "expression": "n / d",
            },
            "time": {"grains": ["day"]},
            "dimensions": [],
        },
    )
    by_id = {
        "propel.n": num,
        "propel.d": den,
        "propel.r": ratio,
        "propel.f": formula,
    }
    r_plan = build_compiled_plan(ratio, by_id)
    f_plan = build_compiled_plan(formula, by_id)
    r_sql = render_plan_sql(r_plan, source="r.yaml")
    f_sql = render_plan_sql(f_plan, source="f.yaml")
    assert "nullif(den.v, 0)" in r_sql
    assert emit_sql(parse_expression("n / d"), {"n": "in_n.v", "d": "in_d.v"}) in f_sql
    # Both produce a day grain block
    assert "grain_day as" in r_sql
    assert "grain_day as" in f_sql


def test_yaml_roundtrip_fixture_loads() -> None:
    # sanity: property module can dump/load a tiny doc
    doc = {"a": 1}
    assert yaml.safe_load(yaml.dump(doc)) == doc
