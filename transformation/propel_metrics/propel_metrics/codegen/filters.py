"""Compile structured filters to SQL boolean expressions."""

from __future__ import annotations

from typing import Any


def _quote_ident(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise ValueError(f"unsafe identifier {name!r}")
    return name


def _sql_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    raise TypeError(f"unsupported literal type {type(value)!r}")


def compile_filter(node: dict[str, Any], *, relation_alias: str = "base") -> str:
    if "sql" in node:
        return f"({node['sql']})"

    if "any_of" in node:
        parts = [
            compile_filter(child, relation_alias=relation_alias)
            for child in node["any_of"]
        ]
        return "(" + " or ".join(parts) + ")"

    if "all_of" in node:
        parts = [
            compile_filter(child, relation_alias=relation_alias)
            for child in node["all_of"]
        ]
        return "(" + " and ".join(parts) + ")"

    if "not" in node:
        inner = compile_filter(node["not"], relation_alias=relation_alias)
        return "(not " + inner + ")"

    field = _quote_ident(node["field"])
    col = f"{relation_alias}.{field}"
    op = node["op"]
    value = node.get("value")

    if op == "eq":
        return f"({col} = {_sql_literal(value)})"
    if op == "neq":
        return f"({col} is distinct from {_sql_literal(value)})"
    if op == "in":
        lits = ", ".join(_sql_literal(v) for v in value)
        return f"({col} in ({lits}))"
    if op == "not_in":
        lits = ", ".join(_sql_literal(v) for v in value)
        return f"({col} not in ({lits}))"
    if op == "gt":
        return f"({col} > {_sql_literal(value)})"
    if op == "gte":
        return f"({col} >= {_sql_literal(value)})"
    if op == "lt":
        return f"({col} < {_sql_literal(value)})"
    if op == "lte":
        return f"({col} <= {_sql_literal(value)})"
    if op == "contains":
        # string substring; array membership uses @>
        return f"({col} like '%' || {_sql_literal(value)} || '%')"
    if op == "not_contains":
        return f"({col} not like '%' || {_sql_literal(value)} || '%')"
    if op == "starts_with":
        return f"({col} like {_sql_literal(value)} || '%')"
    if op == "ends_with":
        return f"({col} like '%' || {_sql_literal(value)})"
    if op == "is_null":
        return f"({col} is null)"
    if op == "is_not_null":
        return f"({col} is not null)"
    raise ValueError(f"unsupported op {op!r}")


def compile_filters(
    filters: list[dict[str, Any]] | None,
    *,
    relation_alias: str = "base",
) -> str | None:
    if not filters:
        return None
    parts = [compile_filter(f, relation_alias=relation_alias) for f in filters]
    return " and ".join(parts)
