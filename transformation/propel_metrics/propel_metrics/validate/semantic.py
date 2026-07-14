"""Semantic validation against the entity catalog."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from propel_metrics.validate.errors import ValidationResult

_OPS_BY_TYPE: dict[str, set[str]] = {
    "string": {
        "eq",
        "neq",
        "in",
        "not_in",
        "contains",
        "not_contains",
        "starts_with",
        "ends_with",
        "is_null",
        "is_not_null",
    },
    "enum": {"eq", "neq", "in", "not_in", "is_null", "is_not_null"},
    "integer": {
        "eq",
        "neq",
        "in",
        "not_in",
        "gt",
        "gte",
        "lt",
        "lte",
        "is_null",
        "is_not_null",
    },
    "float": {
        "eq",
        "neq",
        "in",
        "not_in",
        "gt",
        "gte",
        "lt",
        "lte",
        "is_null",
        "is_not_null",
    },
    "boolean": {"eq", "neq", "is_null", "is_not_null"},
    "timestamp": {"is_null", "is_not_null"},
    "array<string>": {
        "contains",
        "not_contains",
        "is_null",
        "is_not_null",
    },
}

_NULL_OPS = {"is_null", "is_not_null"}
_VISIBILITY_RANK = {"ic": 0, "team": 1, "org": 2}


def _entity(catalog: dict[str, Any], name: str) -> dict[str, Any] | None:
    return catalog.get("entities", {}).get(name)


def _field(catalog: dict[str, Any], entity: str, field: str) -> dict[str, Any] | None:
    ent = _entity(catalog, entity)
    if not ent:
        return None
    return ent.get("fields", {}).get(field)


def _walk_filters(
    node: Any,
    *,
    path: str,
    depth: int,
    result: ValidationResult,
    file: str | None,
    catalog: dict[str, Any],
    entity: str | None,
    advanced: bool,
) -> None:
    if depth > 3:
        result.error(
            "E_FILTER_DEPTH",
            path,
            "filter combinators nest deeper than 3",
            file=file,
        )
        return

    if not isinstance(node, dict):
        result.error("E_FILTER_SHAPE", path, "filter must be an object", file=file)
        return

    if "sql" in node:
        if not advanced:
            result.error(
                "E_ADVANCED_REQUIRED",
                path,
                "sql filters require metadata.advanced: true",
                file=file,
            )
        return

    if "any_of" in node:
        for i, child in enumerate(node["any_of"]):
            _walk_filters(
                child,
                path=f"{path}.any_of[{i}]",
                depth=depth + 1,
                result=result,
                file=file,
                catalog=catalog,
                entity=entity,
                advanced=advanced,
            )
        return

    if "all_of" in node:
        for i, child in enumerate(node["all_of"]):
            _walk_filters(
                child,
                path=f"{path}.all_of[{i}]",
                depth=depth + 1,
                result=result,
                file=file,
                catalog=catalog,
                entity=entity,
                advanced=advanced,
            )
        return

    if "not" in node:
        _walk_filters(
            node["not"],
            path=f"{path}.not",
            depth=depth + 1,
            result=result,
            file=file,
            catalog=catalog,
            entity=entity,
            advanced=advanced,
        )
        return

    field_name = node.get("field")
    op = node.get("op")
    if not entity:
        result.error(
            "E_ENTITY_REQUIRED",
            path,
            "filters require a resolved entity",
            file=file,
        )
        return

    meta = _field(catalog, entity, field_name) if field_name else None
    if meta is None:
        result.error(
            "E_UNKNOWN_FIELD",
            f"{path}.field",
            f"field {field_name!r} not on entity {entity!r}",
            file=file,
        )
        return

    role = meta["role"]
    ftype = meta["type"]
    if op in _NULL_OPS:
        if role not in {"dimension", "event_time", "measure", "key"}:
            result.error(
                "E_FIELD_ROLE",
                f"{path}.field",
                f"field role {role!r} cannot be null-checked",
                file=file,
            )
    elif role != "dimension":
        result.error(
            "E_FIELD_ROLE",
            f"{path}.field",
            f"filters require role dimension (got {role!r})",
            file=file,
        )

    allowed = _OPS_BY_TYPE.get(ftype, set())
    if op not in allowed:
        result.error(
            "E_OP_TYPE",
            f"{path}.op",
            f"op {op!r} incompatible with field type {ftype!r}",
            file=file,
        )
        return

    if op in _NULL_OPS:
        if "value" in node:
            result.error(
                "E_VALUE_TYPE",
                f"{path}.value",
                f"op {op!r} must not include value",
                file=file,
            )
        return

    if "value" not in node:
        result.error(
            "E_VALUE_TYPE",
            f"{path}.value",
            f"op {op!r} requires value",
            file=file,
        )
        return

    value = node["value"]
    if op in {"in", "not_in"}:
        if not isinstance(value, list) or len(value) == 0:
            result.error(
                "E_VALUE_TYPE",
                f"{path}.value",
                f"op {op!r} requires a non-empty array",
                file=file,
            )
            return
        if len(value) > 100:
            result.error(
                "E_VALUE_BOUNDS",
                f"{path}.value",
                "in/not_in lists may have at most 100 elements",
                file=file,
            )
        if ftype == "enum":
            members = set(meta.get("values") or [])
            for i, item in enumerate(value):
                if item not in members:
                    result.error(
                        "E_ENUM_VALUE",
                        f"{path}.value[{i}]",
                        f"{item!r} not in enum {sorted(members)}",
                        file=file,
                    )
        return

    if ftype == "enum":
        members = set(meta.get("values") or [])
        if value not in members:
            result.error(
                "E_ENUM_VALUE",
                f"{path}.value",
                f"{value!r} not in enum {sorted(members)}",
                file=file,
            )


def _validate_measure(
    measure: dict[str, Any],
    *,
    path: str,
    entity: str | None,
    catalog: dict[str, Any],
    advanced: bool,
    result: ValidationResult,
    file: str | None,
) -> None:
    mtype = measure.get("type")
    if mtype == "sql" and not advanced:
        result.error(
            "E_ADVANCED_REQUIRED",
            path,
            "measure.type sql requires metadata.advanced: true",
            file=file,
        )

    if mtype in {"ratio", "formula"}:
        return  # graph + derived checks elsewhere; entity optional

    if not entity:
        result.error(
            "E_ENTITY_REQUIRED",
            path,
            f"measure.type {mtype!r} requires spec.entity",
            file=file,
        )
        return

    if mtype == "count":
        return

    if mtype == "count_distinct":
        fname = measure.get("field")
        meta = _field(catalog, entity, fname)
        if meta is None:
            result.error(
                "E_UNKNOWN_FIELD",
                f"{path}.field",
                f"field {fname!r} not on entity {entity!r}",
                file=file,
            )
        elif meta["role"] not in {"key", "dimension"}:
            result.error(
                "E_FIELD_ROLE",
                f"{path}.field",
                "count_distinct field must have role key or dimension",
                file=file,
            )
        return

    if mtype in {"sum", "avg", "min", "max", "percentile"}:
        fname = measure.get("field")
        meta = _field(catalog, entity, fname)
        if meta is None:
            result.error(
                "E_UNKNOWN_FIELD",
                f"{path}.field",
                f"field {fname!r} not on entity {entity!r}",
                file=file,
            )
        elif meta["role"] != "measure":
            result.error(
                "E_FIELD_ROLE",
                f"{path}.field",
                f"{mtype} field must have role measure",
                file=file,
            )
        return

    if mtype == "interval":
        for key in ("from", "to"):
            fname = measure.get(key)
            meta = _field(catalog, entity, fname)
            if meta is None:
                result.error(
                    "E_UNKNOWN_FIELD",
                    f"{path}.{key}",
                    f"field {fname!r} not on entity {entity!r}",
                    file=file,
                )
            elif meta["role"] != "event_time":
                result.error(
                    "E_FIELD_ROLE",
                    f"{path}.{key}",
                    "interval endpoints must have role event_time",
                    file=file,
                )
        if "join" in measure:
            result.error(
                "E_RESERVED",
                f"{path}.join",
                "measure.join is reserved for v2",
                file=file,
            )


def _validate_time(
    time_spec: dict[str, Any],
    *,
    path: str,
    entity: str | None,
    measure_type: str | None,
    catalog: dict[str, Any],
    result: ValidationResult,
    file: str | None,
) -> None:
    grains = time_spec.get("grains") or []
    windows = time_spec.get("windows") or []
    if not grains and not windows:
        result.error(
            "E_TIME_REQUIRED",
            path,
            "time must declare grains and/or windows",
            file=file,
        )

    field_name = time_spec.get("field")
    derived = measure_type in {"ratio", "formula"}
    if derived:
        if field_name is not None:
            result.error(
                "E_TIME_FIELD",
                f"{path}.field",
                "ratio/formula metrics must omit time.field (operands own it)",
                file=file,
            )
        return

    if not field_name:
        result.error(
            "E_TIME_FIELD",
            f"{path}.field",
            "time.field is required for non-derived metrics",
            file=file,
        )
        return

    if not entity:
        return

    meta = _field(catalog, entity, field_name)
    if meta is None:
        result.error(
            "E_UNKNOWN_FIELD",
            f"{path}.field",
            f"field {field_name!r} not on entity {entity!r}",
            file=file,
        )
    elif meta["role"] != "event_time":
        result.error(
            "E_FIELD_ROLE",
            f"{path}.field",
            "time.field must have role event_time",
            file=file,
        )


def _validate_dimensions(
    dims: list[str],
    *,
    path: str,
    entity: str | None,
    catalog: dict[str, Any],
    result: ValidationResult,
    file: str | None,
) -> None:
    if not dims:
        return
    if not entity:
        result.error(
            "E_ENTITY_REQUIRED",
            path,
            "dimensions require a resolved entity",
            file=file,
        )
        return

    card = catalog.get("cardinality") or {}
    warn_above = card.get("warn_above", 500)
    error_above = card.get("error_above", 5000)

    for i, dim in enumerate(dims):
        meta = _field(catalog, entity, dim)
        dpath = f"{path}[{i}]"
        if meta is None:
            result.error(
                "E_UNKNOWN_FIELD",
                dpath,
                f"dimension {dim!r} not on entity {entity!r}",
                file=file,
            )
            continue
        if meta["role"] != "dimension":
            result.error(
                "E_FIELD_ROLE",
                dpath,
                f"dimension {dim!r} must have role dimension",
                file=file,
            )
            continue
        estimate = meta.get("cardinality_estimate")
        if estimate is not None:
            if estimate > error_above:
                result.error(
                    "E_CARDINALITY",
                    dpath,
                    f"dimension {dim!r} cardinality estimate {estimate} exceeds "
                    f"hard cap {error_above}",
                    file=file,
                )
            elif estimate > warn_above:
                result.warn(
                    "W_CARDINALITY",
                    dpath,
                    f"dimension {dim!r} cardinality estimate {estimate} exceeds "
                    f"warn threshold {warn_above}",
                    file=file,
                )


def validate_metric_semantic(
    doc: dict[str, Any],
    catalog: dict[str, Any],
    *,
    file: str | None = None,
    parent_doc: dict[str, Any] | None = None,
) -> ValidationResult:
    result = ValidationResult()
    if doc.get("kind") != "Metric":
        return result

    meta = doc.get("metadata") or {}
    spec = doc.get("spec") or {}
    advanced = bool(meta.get("advanced", False))
    entity = spec.get("entity")
    measure = spec.get("measure")
    extends = spec.get("extends")

    if extends and "overrides" not in spec and measure is None and entity is None:
        # bare extends ok if overrides carry measure — checked after resolve
        pass

    if measure is None and not extends:
        result.error(
            "E_MEASURE_REQUIRED",
            "spec.measure",
            "measure is required unless extends is set",
            file=file,
        )

    measure_type = (measure or {}).get("type") if measure else None
    if parent_doc and extends:
        parent_vis = (parent_doc.get("spec") or {}).get("visibility", "team")
        overrides = spec.get("overrides") or {}
        # Child may set visibility on the spec root or under overrides.
        if "visibility" in spec:
            child_vis = spec["visibility"]
            vis_path = "spec.visibility"
        elif "visibility" in overrides:
            child_vis = overrides["visibility"]
            vis_path = "spec.overrides.visibility"
        else:
            child_vis = parent_vis
            vis_path = "spec.visibility"
        if _VISIBILITY_RANK.get(child_vis, 1) > _VISIBILITY_RANK.get(parent_vis, 1):
            result.error(
                "E_VISIBILITY_ESCALATION",
                vis_path,
                f"extends child visibility {child_vis!r} broader than parent "
                f"{parent_vis!r}",
                file=file,
            )

    if entity and _entity(catalog, entity) is None:
        result.error(
            "E_UNKNOWN_ENTITY",
            "spec.entity",
            f"unknown entity {entity!r}",
            file=file,
        )

    if measure:
        _validate_measure(
            measure,
            path="spec.measure",
            entity=entity,
            catalog=catalog,
            advanced=advanced,
            result=result,
            file=file,
        )

    for i, filt in enumerate(spec.get("filters") or []):
        _walk_filters(
            filt,
            path=f"spec.filters[{i}]",
            depth=1,
            result=result,
            file=file,
            catalog=catalog,
            entity=entity,
            advanced=advanced,
        )

    if "time" in spec:
        _validate_time(
            spec["time"],
            path="spec.time",
            entity=entity,
            measure_type=measure_type,
            catalog=catalog,
            result=result,
            file=file,
        )

    _validate_dimensions(
        list(spec.get("dimensions") or []),
        path="spec.dimensions",
        entity=entity,
        catalog=catalog,
        result=result,
        file=file,
    )

    # params bind targets must reference dimension fields on the entity
    for pname, pdecl in (spec.get("params") or {}).items():
        bind = (pdecl.get("binds") or {}).get("filter") or {}
        bfield = bind.get("field")
        if entity and bfield and _field(catalog, entity, bfield) is None:
            result.error(
                "E_UNKNOWN_FIELD",
                f"spec.params.{pname}.binds.filter.field",
                f"param bind field {bfield!r} not on entity {entity!r}",
                file=file,
            )

    return result


def validate_files_semantic(
    docs: list[tuple[Path, dict[str, Any]]],
    catalog: dict[str, Any],
) -> ValidationResult:
    result = ValidationResult()
    by_id = {
        (d.get("metadata") or {}).get("id"): d
        for _, d in docs
        if d.get("kind") == "Metric"
    }
    for path, doc in docs:
        parent = None
        extends = (doc.get("spec") or {}).get("extends")
        if extends:
            parent = by_id.get(extends)
        result.extend(
            validate_metric_semantic(doc, catalog, file=str(path), parent_doc=parent)
        )
    return result
