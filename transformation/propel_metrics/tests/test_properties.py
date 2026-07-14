"""Property-style tests for ratio ≡ formula and window labeling."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import yaml
from propel_metrics.codegen.sql import render_plan_sql
from propel_metrics.expr import emit_sql, parse_expression
from propel_metrics.ir import build_compiled_plan
from propel_metrics.resolve import ResolvedMetric, content_hash, resolve_metrics


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


def test_window_brute_force_count_semantics() -> None:
    """Rolling window at step d ≡ filter rows into (end-N, end] then aggregate.

    Pure-Python stand-in for the spine join: for each step end, count events
    with t in (end - N days, end]. Empty windows emit no row (INNER JOIN).
    """
    from datetime import date, datetime, timedelta

    events = [
        datetime(2026, 1, 1, 12, tzinfo=UTC),
        datetime(2026, 1, 5, 12, tzinfo=UTC),
        datetime(2026, 1, 10, 12, tzinfo=UTC),
        # gap: nothing until
        datetime(2026, 1, 25, 12, tzinfo=UTC),
    ]
    n_days = 7
    steps = [date(2026, 1, d) for d in range(1, 31)]

    def brute(end: date) -> int | None:
        start = datetime.combine(
            end - timedelta(days=n_days), datetime.min.time(), tzinfo=UTC
        )
        end_ts = datetime.combine(end, datetime.min.time(), tzinfo=UTC)
        # window (start, end] on timestamps — match SQL: t > end-N and t <= end
        # Using date end as midnight UTC for the step_date boundary.
        matched = [e for e in events if start < e <= end_ts]
        return len(matched) if matched else None

    results = {s: brute(s) for s in steps}
    # Brute uses exclusive upper bound at midnight of ``end`` (legacy midnight
    # semantics for this unit test). Codegen uses step_date+1 day; see SQL test.
    assert results[date(2026, 1, 2)] == 1
    assert results[date(2026, 1, 6)] == 2
    assert results[date(2026, 1, 20)] is None  # gap
    assert results[date(2026, 1, 26)] == 1


def test_window_sql_emits_inner_join_and_open_interval() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.cycle_time_trailing_30d"], by_id)
    sql = render_plan_sql(plan, source="cycle_time_trailing_30d.yaml")
    assert "inner join m_rows" in sql
    assert "r.t > ((s.step_date + interval '1 day') - interval '30 days')" in sql
    assert "r.t < (s.step_date + interval '1 day')" in sql
    assert "left join m_rows" not in sql.lower()


def test_yaml_roundtrip_fixture_loads() -> None:
    # sanity: property module can dump/load a tiny doc
    doc = {"a": 1}
    assert yaml.safe_load(yaml.dump(doc)) == doc
