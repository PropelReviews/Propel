"""Intermediate representation between resolve and SQL codegen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from propel_metrics.expr.parse import ExprAST


@dataclass(frozen=True, slots=True)
class Window:
    days: int
    step: str  # day | week


@dataclass(frozen=True, slots=True)
class AggSpec:
    """How to aggregate the operand `_value` column."""

    method: str  # count | count_distinct | sum | avg | min | max | percentile
    percentile: float | None = None  # 0-100 when method == percentile


@dataclass(frozen=True, slots=True)
class OperandPlan:
    """One unaggregated row source."""

    entity: str
    dbt_model: str
    filters: tuple[dict[str, Any], ...]
    time_field: str
    # SQL select list fragments relative to alias `base`, excluding tenant_id/time/dims
    value_sql: str  # e.g. "1 as _value" or interval extract
    # Extra WHERE clauses (interval null/negative handling), already SQL
    extra_where: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AggregationPlan:
    operand: OperandPlan
    agg: AggSpec


@dataclass(frozen=True, slots=True)
class CompiledPlan:
    metric_id: str
    definition_version: str
    kind: Literal["simple", "ratio", "formula"]
    aggregations: dict[str, AggregationPlan]
    expression: ExprAST | None
    dimensions: tuple[str, ...]
    grains: tuple[str, ...]
    windows: tuple[Window, ...]
    zero_denominator: Literal["null", "zero"] | None
