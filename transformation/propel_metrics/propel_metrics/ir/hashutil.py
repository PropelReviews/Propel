"""Canonical JSON helpers for CompiledPlan (M4 hashing will reuse)."""

from __future__ import annotations

import json
from typing import Any

from propel_metrics.expr.parse import BinOp, Name, Number, UnaryOp
from propel_metrics.ir.types import CompiledPlan


def _expr_to_json(node: Any) -> Any:
    if isinstance(node, Number):
        return {"type": "number", "value": node.value}
    if isinstance(node, Name):
        return {"type": "name", "name": node.name}
    if isinstance(node, UnaryOp):
        return {
            "type": "unary",
            "op": node.op,
            "operand": _expr_to_json(node.operand),
        }
    if isinstance(node, BinOp):
        return {
            "type": "binary",
            "op": node.op,
            "left": _expr_to_json(node.left),
            "right": _expr_to_json(node.right),
        }
    raise TypeError(type(node))


def plan_to_canonical_dict(plan: CompiledPlan) -> dict[str, Any]:
    aggs: dict[str, Any] = {}
    for name, ap in sorted(plan.aggregations.items()):
        op = ap.operand
        aggs[name] = {
            "agg": {"method": ap.agg.method, "percentile": ap.agg.percentile},
            "operand": {
                "entity": op.entity,
                "dbt_model": op.dbt_model,
                "filters": list(op.filters),
                "time_field": op.time_field,
                "value_sql": op.value_sql,
                "extra_where": list(op.extra_where),
            },
        }
    return {
        "aggregations": aggs,
        "definition_version": plan.definition_version,
        "dimensions": list(plan.dimensions),
        "expression": (
            _expr_to_json(plan.expression) if plan.expression is not None else None
        ),
        "grains": list(plan.grains),
        "kind": plan.kind,
        "metric_id": plan.metric_id,
        "windows": [{"days": w.days, "step": w.step} for w in plan.windows],
        "zero_denominator": plan.zero_denominator,
    }


def plan_canonical_json(plan: CompiledPlan) -> str:
    return json.dumps(
        plan_to_canonical_dict(plan), sort_keys=True, separators=(",", ":")
    )
