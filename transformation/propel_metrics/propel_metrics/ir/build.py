"""Build CompiledPlan IR from ResolvedMetric (+ operand index)."""

from __future__ import annotations

from typing import Any

from propel_metrics.expr.parse import collect_names, parse_expression
from propel_metrics.ir.types import (
    AggregationPlan,
    AggSpec,
    CompiledPlan,
    MappedDim,
    OperandPlan,
    Window,
)
from propel_metrics.resolve import ResolvedMetric
from propel_metrics.validate.loader import load_catalog

_SIMPLE_TYPES = {
    "count",
    "count_distinct",
    "sum",
    "avg",
    "min",
    "max",
    "percentile",
    "interval",
}

def _all_catalog_dims() -> frozenset[str]:
    """Entity fields with role=dimension (native columns; no mapping required)."""
    catalog = load_catalog()
    out: set[str] = set()
    for ent in (catalog.get("entities") or {}).values():
        for name, meta in (ent.get("fields") or {}).items():
            if isinstance(meta, dict) and meta.get("role") == "dimension":
                out.add(name)
    return frozenset(out)


def _dbt_model(entity: str) -> str:
    catalog = load_catalog()
    return catalog["entities"][entity]["dbt_model"]


def _value_sql(measure: dict[str, Any]) -> str:
    mtype = measure["type"]
    if mtype == "count":
        return "1 as _value"
    if mtype == "count_distinct":
        return f"base.{measure['field']} as _value"
    if mtype in {"sum", "avg", "min", "max", "percentile"}:
        return f"base.{measure['field']} as _value"
    if mtype == "interval":
        frm = measure["from"]
        to = measure["to"]
        if measure.get("negative_handling") == "clamp_zero":
            return (
                f"greatest(extract(epoch from (base.{to} - base.{frm}))"
                f"::float8, 0) as _value"
            )
        return f"extract(epoch from (base.{to} - base.{frm}))::float8 as _value"
    raise ValueError(f"cannot build value_sql for measure type {mtype!r}")


def _extra_where(measure: dict[str, Any]) -> tuple[str, ...]:
    if measure.get("type") != "interval":
        return ()
    clauses: list[str] = []
    frm = measure["from"]
    to = measure["to"]
    if measure.get("null_handling", "exclude") == "exclude":
        clauses.append(f"(base.{frm} is not null)")
        clauses.append(f"(base.{to} is not null)")
    if measure.get("negative_handling", "exclude") == "exclude":
        clauses.append(f"(base.{to} >= base.{frm})")
    return tuple(clauses)


def _agg_spec(measure: dict[str, Any]) -> AggSpec:
    mtype = measure["type"]
    if mtype == "count":
        return AggSpec(method="count")
    if mtype == "count_distinct":
        return AggSpec(method="count_distinct")
    if mtype in {"sum", "avg", "min", "max"}:
        return AggSpec(method=mtype)
    if mtype == "percentile":
        return AggSpec(method="percentile", percentile=float(measure["percentile"]))
    if mtype == "interval":
        agg = measure["agg"]
        if agg == "median":
            return AggSpec(method="percentile", percentile=50.0)
        if agg == "percentile":
            return AggSpec(method="percentile", percentile=float(measure["percentile"]))
        if agg in {"avg", "min", "max", "sum"}:
            return AggSpec(method=agg)
    raise ValueError(f"unsupported measure for AggSpec: {measure!r}")


def _operand_from_spec(
    spec: dict[str, Any],
    *,
    extra_filters: list[dict[str, Any]] | None = None,
    mapped_dimensions: tuple[MappedDim, ...] = (),
) -> OperandPlan:
    entity = spec["entity"]
    measure = spec["measure"]
    if measure["type"] not in _SIMPLE_TYPES:
        raise ValueError(f"operand measure must be simple, got {measure['type']!r}")
    filters = list(spec.get("filters") or [])
    if extra_filters:
        filters.extend(extra_filters)
    return OperandPlan(
        entity=entity,
        dbt_model=_dbt_model(entity),
        filters=tuple(filters),
        time_field=spec["time"]["field"],
        value_sql=_value_sql(measure),
        extra_where=_extra_where(measure),
        mapped_dimensions=mapped_dimensions,
    )


def _aggregation_from_spec(
    spec: dict[str, Any],
    *,
    extra_filters: list[dict[str, Any]] | None = None,
    mapped_dimensions: tuple[MappedDim, ...] = (),
) -> AggregationPlan:
    return AggregationPlan(
        operand=_operand_from_spec(
            spec,
            extra_filters=extra_filters,
            mapped_dimensions=mapped_dimensions,
        ),
        agg=_agg_spec(spec["measure"]),
    )


def _windows(spec: dict[str, Any]) -> tuple[Window, ...]:
    raw = (spec.get("time") or {}).get("windows") or []
    return tuple(Window(days=int(w["days"]), step=str(w["step"])) for w in raw)


def _grains(spec: dict[str, Any]) -> tuple[str, ...]:
    return tuple((spec.get("time") or {}).get("grains") or [])


def _dimensions(
    spec: dict[str, Any],
    *,
    mapped_by_name: dict[str, MappedDim] | None = None,
) -> tuple[str, ...]:
    dims = tuple(spec.get("dimensions") or [])
    mapped_by_name = mapped_by_name or {}
    catalog_dims = _all_catalog_dims()
    for dim in dims:
        if dim in catalog_dims or dim in mapped_by_name:
            continue
        raise ValueError(
            f"unsupported dimension {dim!r}; "
            f"catalog={sorted(catalog_dims)} mapped={sorted(mapped_by_name)}"
        )
    return dims


def _mappings_for_dims(
    dimensions: tuple[str, ...],
    mapped_by_name: dict[str, MappedDim],
) -> tuple[MappedDim, ...]:
    return tuple(mapped_by_name[d] for d in dimensions if d in mapped_by_name)


def build_compiled_plan(
    metric: ResolvedMetric,
    by_id: dict[str, ResolvedMetric],
    *,
    mapped_dimensions: dict[str, MappedDim] | None = None,
) -> CompiledPlan:
    """Construct IR; enforces derived-of-simple and dim/entity invariants.

    ``mapped_dimensions`` maps dimension name → MappedDim for org DimensionMappings.
    """
    spec = metric.spec
    measure = spec.get("measure") or {}
    mtype = measure.get("type")
    mapped_by_name = mapped_dimensions or {}
    dimensions = _dimensions(spec, mapped_by_name=mapped_by_name)
    grains = _grains(spec)
    windows = _windows(spec)
    operand_maps = _mappings_for_dims(dimensions, mapped_by_name)

    if mtype in _SIMPLE_TYPES:
        return CompiledPlan(
            metric_id=metric.metric_id,
            definition_version=metric.definition_version,
            kind="simple",
            aggregations={
                "value": _aggregation_from_spec(spec, mapped_dimensions=operand_maps)
            },
            expression=None,
            dimensions=dimensions,
            grains=grains,
            windows=windows,
            zero_denominator=None,
        )

    if mtype == "ratio":
        aggregations: dict[str, AggregationPlan] = {}
        entities: set[str] = set()
        for side in ("numerator", "denominator"):
            op = measure[side]
            ref = op["ref"]
            if ref not in by_id:
                raise ValueError(f"{metric.metric_id}: missing operand ref {ref!r}")
            parent = by_id[ref]
            pmeasure = (parent.spec.get("measure") or {}).get("type")
            if pmeasure not in _SIMPLE_TYPES:
                raise ValueError(
                    f"{metric.metric_id}: operand {ref!r} is not simple "
                    f"(got {pmeasure!r})"
                )
            if dimensions:
                parent_dims = set(parent.spec.get("dimensions") or [])
                entity_fields = _entity_dim_fields(parent.spec["entity"]) | set(
                    mapped_by_name
                )
                if not set(dimensions).issubset(parent_dims) and not set(
                    dimensions
                ).issubset(entity_fields):
                    # Allow dims that exist on the entity even if parent declared []
                    missing = [d for d in dimensions if d not in entity_fields]
                    if missing:
                        raise ValueError(
                            f"{metric.metric_id}: dimension(s) {missing} not on "
                            f"operand entity {parent.spec['entity']!r}"
                        )
            entities.add(parent.spec["entity"])
            overrides = (op.get("overrides") or {}).get("filters") or []
            aggregations["num" if side == "numerator" else "den"] = (
                _aggregation_from_spec(
                    parent.spec,
                    extra_filters=list(overrides),
                    mapped_dimensions=operand_maps,
                )
            )
        if dimensions and len(entities) > 1:
            raise ValueError(
                f"{metric.metric_id}: dimensional ratio requires one entity; "
                f"got {sorted(entities)}"
            )
        zd = measure.get("zero_denominator", None)
        zero_denominator: str | None
        if zd is None:
            zero_denominator = "null"
        elif zd == "zero":
            zero_denominator = "zero"
        else:
            raise ValueError(f"invalid zero_denominator {zd!r}")
        return CompiledPlan(
            metric_id=metric.metric_id,
            definition_version=metric.definition_version,
            kind="ratio",
            aggregations=aggregations,
            expression=None,
            dimensions=dimensions,
            grains=grains,
            windows=windows,
            zero_denominator=zero_denominator,  # type: ignore[arg-type]
        )

    if mtype == "formula":
        aggregations = {}
        entities = set()
        for name, op in (measure.get("inputs") or {}).items():
            ref = op["ref"]
            if ref not in by_id:
                raise ValueError(f"{metric.metric_id}: missing input ref {ref!r}")
            parent = by_id[ref]
            pmeasure = (parent.spec.get("measure") or {}).get("type")
            if pmeasure not in _SIMPLE_TYPES:
                raise ValueError(
                    f"{metric.metric_id}: input {ref!r} is not simple "
                    f"(got {pmeasure!r})"
                )
            if dimensions:
                entity_fields = _entity_dim_fields(parent.spec["entity"]) | set(
                    mapped_by_name
                )
                missing = [d for d in dimensions if d not in entity_fields]
                if missing:
                    raise ValueError(
                        f"{metric.metric_id}: dimension(s) {missing} not on "
                        f"input entity {parent.spec['entity']!r}"
                    )
            entities.add(parent.spec["entity"])
            overrides = (op.get("overrides") or {}).get("filters") or []
            aggregations[name] = _aggregation_from_spec(
                parent.spec,
                extra_filters=list(overrides),
                mapped_dimensions=operand_maps,
            )
        if dimensions and len(entities) > 1:
            raise ValueError(
                f"{metric.metric_id}: dimensional formula requires one entity; "
                f"got {sorted(entities)}"
            )
        expr = parse_expression(measure["expression"])
        unknown = collect_names(expr) - set(aggregations)
        if unknown:
            raise ValueError(
                f"{metric.metric_id}: expression references unknown inputs "
                f"{sorted(unknown)}"
            )
        return CompiledPlan(
            metric_id=metric.metric_id,
            definition_version=metric.definition_version,
            kind="formula",
            aggregations=aggregations,
            expression=expr,
            dimensions=dimensions,
            grains=grains,
            windows=windows,
            zero_denominator=None,
        )

    raise ValueError(f"{metric.metric_id}: unsupported measure type {mtype!r}")


def _entity_dim_fields(entity: str) -> set[str]:
    catalog = load_catalog()
    fields = catalog["entities"][entity]["fields"]
    return {name for name, meta in fields.items() if meta.get("role") == "dimension"}
