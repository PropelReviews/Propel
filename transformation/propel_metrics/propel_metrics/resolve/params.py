"""Bind MetricSet params into metric filter predicates."""

from __future__ import annotations

import copy
from typing import Any


class ParamBindError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _type_ok(declared: str, value: Any) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "array<string>":
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    return False


def bind_params(
    spec: dict[str, Any],
    param_values: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a deep-copied spec with declared params materialized into filters.

    Unknown keys in ``param_values`` raise ``E_UNKNOWN_PARAM``.
    Missing values without defaults raise ``E_PARAM_REQUIRED``.
    Type mismatches raise ``E_PARAM_TYPE``.
    After binding, ``params`` is removed from the returned spec so hashes
    reflect bound filters only.
    """
    out = copy.deepcopy(spec)
    decls: dict[str, Any] = dict(out.get("params") or {})
    values = dict(param_values or {})

    for key in values:
        if key not in decls:
            raise ParamBindError(
                "E_UNKNOWN_PARAM",
                f"param {key!r} is not declared on the metric",
            )

    filters = list(out.get("filters") or [])
    for name, decl in decls.items():
        if name in values:
            value = values[name]
        elif "default" in decl:
            value = decl["default"]
        else:
            raise ParamBindError(
                "E_PARAM_REQUIRED",
                f"param {name!r} has no value and no default",
            )
        if not _type_ok(decl["type"], value):
            raise ParamBindError(
                "E_PARAM_TYPE",
                f"param {name!r} expected {decl['type']}, got {type(value).__name__}",
            )
        bind = (decl.get("binds") or {}).get("filter") or {}
        field = bind.get("field")
        op = bind.get("op")
        if not field or not op:
            raise ParamBindError(
                "E_PARAM_TYPE",
                f"param {name!r} binds.filter requires field and op",
            )
        filters.append({"field": field, "op": op, "value": value})

    out["filters"] = filters
    out.pop("params", None)
    return out
