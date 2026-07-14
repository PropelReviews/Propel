"""Formula expression parser / emit tests."""

from __future__ import annotations

import pytest
from propel_metrics.expr import (
    FormulaSyntaxError,
    collect_names,
    emit_sql,
    parse_expression,
)


def test_parse_and_emit_ratio_like() -> None:
    tree = parse_expression("a / b")
    assert collect_names(tree) == {"a", "b"}
    sql = emit_sql(tree, {"a": "in_a.v", "b": "in_b.v"})
    assert sql == "((in_a.v) / nullif((in_b.v), 0))"


def test_parse_precedence() -> None:
    tree = parse_expression("a + b * c")
    sql = emit_sql(tree, {"a": "a", "b": "b", "c": "c"})
    assert sql == "((a) + (((b) * (c))))"


def test_unary_minus() -> None:
    tree = parse_expression("-a + 2")
    sql = emit_sql(tree, {"a": "x"})
    assert "(-(x))" in sql
    assert "2::float8" in sql


def test_syntax_error() -> None:
    with pytest.raises(FormulaSyntaxError):
        parse_expression("a +")


def test_unknown_column() -> None:
    tree = parse_expression("a / b")
    with pytest.raises(KeyError):
        emit_sql(tree, {"a": "a"})
