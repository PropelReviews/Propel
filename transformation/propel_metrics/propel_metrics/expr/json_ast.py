"""Normalize Python formula ASTs to the TS FormulaAST JSON shape."""

from __future__ import annotations

from typing import Any

from propel_metrics.expr.parse import (
    BinOp,
    FormulaSyntaxError,
    Name,
    Number,
    UnaryOp,
    parse_expression,
)


def ast_to_json(node: object) -> dict[str, Any]:
    if isinstance(node, Number):
        return {"type": "number", "value": float(node.value)}
    if isinstance(node, Name):
        return {"type": "name", "name": node.name}
    if isinstance(node, UnaryOp):
        return {"type": "unary", "op": node.op, "operand": ast_to_json(node.operand)}
    if isinstance(node, BinOp):
        return {
            "type": "binary",
            "op": node.op,
            "left": ast_to_json(node.left),
            "right": ast_to_json(node.right),
        }
    raise TypeError(f"unknown node {type(node)!r}")


def try_parse_json(expr: str) -> dict[str, Any]:
    try:
        return {"ok": True, "ast": ast_to_json(parse_expression(expr))}
    except (FormulaSyntaxError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
