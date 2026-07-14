"""Golden IR → SQL string compares (normalized whitespace)."""

from __future__ import annotations

import re
from pathlib import Path

from propel_metrics.codegen.sql import render_plan_sql
from propel_metrics.ir import build_compiled_plan
from propel_metrics.resolve import resolve_metrics

GOLDENS = Path(__file__).parent / "goldens"


def _norm(sql: str) -> str:
    # Collapse whitespace; keep ref()/config tokens intact.
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]+", " ", sql)).strip() + "\n"


def _assert_golden(name: str, sql: str) -> None:
    path = GOLDENS / name
    normalized = _norm(sql)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(normalized, encoding="utf-8")
        raise AssertionError(f"wrote missing golden {path}; re-run tests")
    expected = path.read_text(encoding="utf-8")
    assert normalized == expected, f"golden drift in {name}"


def test_golden_count_merged_prs() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.merged_prs"], by_id)
    _assert_golden(
        "merged_prs.sql",
        render_plan_sql(plan, source="merged_prs.yaml"),
    )


def test_golden_interval_cycle_time() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.cycle_time"], by_id)
    _assert_golden(
        "cycle_time.sql",
        render_plan_sql(plan, source="cycle_time.yaml"),
    )


def test_golden_ratio_cfr() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.change_failure_rate"], by_id)
    _assert_golden(
        "change_failure_rate.sql",
        render_plan_sql(plan, source="change_failure_rate.yaml"),
    )


def test_golden_window_trailing_30d() -> None:
    by_id = {m.metric_id: m for m in resolve_metrics(active_only=True)}
    plan = build_compiled_plan(by_id["propel.cycle_time_trailing_30d"], by_id)
    _assert_golden(
        "cycle_time_trailing_30d.sql",
        render_plan_sql(plan, source="cycle_time_trailing_30d.yaml"),
    )
