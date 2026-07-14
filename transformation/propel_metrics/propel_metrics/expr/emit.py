"""Emit SQL fragments from formula ExprAST."""

from __future__ import annotations

from propel_metrics.expr.parse import BinOp, ExprAST, Name, Number, UnaryOp


def emit_sql(node: ExprAST, columns: dict[str, str]) -> str:
    """Map AST to SQL. ``columns`` maps input name → SQL column expression."""
    if isinstance(node, Number):
        # Normalize ints without trailing .0 noise when exact
        v = node.value
        if v == int(v):
            return f"{int(v)}::float8"
        return f"{v}::float8"
    if isinstance(node, Name):
        if node.name not in columns:
            raise KeyError(f"unknown input {node.name!r}")
        return columns[node.name]
    if isinstance(node, UnaryOp):
        if node.op != "-":
            raise ValueError(f"unsupported unary op {node.op!r}")
        return f"(-({emit_sql(node.operand, columns)}))"
    if isinstance(node, BinOp):
        left = emit_sql(node.left, columns)
        right = emit_sql(node.right, columns)
        if node.op == "/":
            return f"(({left}) / nullif(({right}), 0))"
        if node.op in {"+", "-", "*"}:
            return f"(({left}) {node.op} ({right}))"
        raise ValueError(f"unsupported binary op {node.op!r}")
    raise TypeError(type(node))
