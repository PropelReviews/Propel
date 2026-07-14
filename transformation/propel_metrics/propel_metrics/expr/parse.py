"""Formula expression tokenizer + recursive-descent parser.

Grammar (design §4.4 subset):
  expr   := term (("+" | "-") term)*
  term   := factor (("*" | "/") factor)*
  factor := NUMBER | NAME | "(" expr ")" | "-" factor
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Number:
    value: float


@dataclass(frozen=True, slots=True)
class Name:
    name: str


@dataclass(frozen=True, slots=True)
class UnaryOp:
    op: str
    operand: ExprAST


@dataclass(frozen=True, slots=True)
class BinOp:
    op: str
    left: ExprAST
    right: ExprAST


ExprAST = Number | Name | UnaryOp | BinOp

_TOKEN = re.compile(
    r"""
    \s*(?:
        (?P<number>\d+(?:\.\d*)?|\.\d+)
      | (?P<name>[a-z][a-z0-9_]*)
      | (?P<op>[+\-*/()])
    )
    """,
    re.VERBOSE,
)


class FormulaSyntaxError(ValueError):
    """Raised when a formula expression cannot be parsed."""


def tokenize(source: str) -> list[tuple[str, str]]:
    pos = 0
    tokens: list[tuple[str, str]] = []
    while pos < len(source):
        m = _TOKEN.match(source, pos)
        if not m:
            raise FormulaSyntaxError(
                f"unexpected character at position {pos}: {source[pos]!r}"
            )
        pos = m.end()
        if m.lastgroup == "number":
            tokens.append(("number", m.group("number")))
        elif m.lastgroup == "name":
            tokens.append(("name", m.group("name")))
        else:
            tokens.append(("op", m.group("op")))
    return tokens


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.i = 0

    def peek(self) -> tuple[str, str] | None:
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def consume(
        self, kind: str | None = None, value: str | None = None
    ) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise FormulaSyntaxError("unexpected end of expression")
        if kind is not None and tok[0] != kind:
            raise FormulaSyntaxError(f"expected {kind}, got {tok}")
        if value is not None and tok[1] != value:
            raise FormulaSyntaxError(f"expected {value!r}, got {tok[1]!r}")
        self.i += 1
        return tok

    def parse(self) -> ExprAST:
        node = self.expr()
        if self.peek() is not None:
            raise FormulaSyntaxError(f"trailing tokens: {self.tokens[self.i :]}")
        return node

    def expr(self) -> ExprAST:
        node = self.term()
        while True:
            tok = self.peek()
            if tok is None or tok[0] != "op" or tok[1] not in {"+", "-"}:
                return node
            op = self.consume()[1]
            node = BinOp(op=op, left=node, right=self.term())

    def term(self) -> ExprAST:
        node = self.factor()
        while True:
            tok = self.peek()
            if tok is None or tok[0] != "op" or tok[1] not in {"*", "/"}:
                return node
            op = self.consume()[1]
            node = BinOp(op=op, left=node, right=self.factor())

    def factor(self) -> ExprAST:
        tok = self.peek()
        if tok is None:
            raise FormulaSyntaxError("unexpected end of expression")
        if tok[0] == "op" and tok[1] == "-":
            self.consume()
            return UnaryOp(op="-", operand=self.factor())
        if tok[0] == "op" and tok[1] == "(":
            self.consume()
            node = self.expr()
            self.consume("op", ")")
            return node
        if tok[0] == "number":
            self.consume()
            return Number(value=float(tok[1]))
        if tok[0] == "name":
            self.consume()
            return Name(name=tok[1])
        raise FormulaSyntaxError(f"unexpected token {tok}")


def parse_expression(source: str) -> ExprAST:
    text = source.strip()
    if not text:
        raise FormulaSyntaxError("empty expression")
    return _Parser(tokenize(text)).parse()


def collect_names(node: ExprAST) -> set[str]:
    if isinstance(node, Number):
        return set()
    if isinstance(node, Name):
        return {node.name}
    if isinstance(node, UnaryOp):
        return collect_names(node.operand)
    if isinstance(node, BinOp):
        return collect_names(node.left) | collect_names(node.right)
    raise TypeError(type(node))
