/**
 * Formula expression tokenizer + recursive-descent parser.
 * Grammar mirrors propel_metrics.expr.parse (keep in sync; property-tested later).
 *
 *   expr   := term (("+" | "-") term)*
 *   term   := factor (("*" | "/") factor)*
 *   factor := NUMBER | NAME | "(" expr ")" | "-" factor
 */

export type FormulaAST =
  | { type: "number"; value: number }
  | { type: "name"; name: string }
  | { type: "unary"; op: "-"; operand: FormulaAST }
  | { type: "binary"; op: "+" | "-" | "*" | "/"; left: FormulaAST; right: FormulaAST };

export class FormulaSyntaxError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "FormulaSyntaxError";
  }
}

type Token = { kind: "number" | "name" | "op"; value: string };

const TOKEN = /\s*(?:(\d+(?:\.\d*)?|\.\d+)|([a-z][a-z0-9_]*)|([+\-*/()]))/y;

export function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  TOKEN.lastIndex = 0;
  let pos = 0;
  while (pos < source.length) {
    TOKEN.lastIndex = pos;
    const m = TOKEN.exec(source);
    if (!m || m.index !== pos) {
      throw new FormulaSyntaxError(
        `unexpected character at position ${pos}: ${JSON.stringify(source[pos])}`,
      );
    }
    pos = TOKEN.lastIndex;
    if (m[1] !== undefined) tokens.push({ kind: "number", value: m[1] });
    else if (m[2] !== undefined) tokens.push({ kind: "name", value: m[2] });
    else tokens.push({ kind: "op", value: m[3]! });
  }
  return tokens;
}

class Parser {
  i = 0;
  constructor(private tokens: Token[]) {}

  peek(): Token | undefined {
    return this.tokens[this.i];
  }

  consume(): Token {
    const t = this.tokens[this.i++];
    if (!t) throw new FormulaSyntaxError("unexpected end of expression");
    return t;
  }

  parse(): FormulaAST {
    const expr = this.expr();
    if (this.peek()) {
      throw new FormulaSyntaxError(`unexpected token ${this.peek()!.value}`);
    }
    return expr;
  }

  expr(): FormulaAST {
    let left = this.term();
    while (
      this.peek()?.kind === "op" &&
      (this.peek()!.value === "+" || this.peek()!.value === "-")
    ) {
      const op = this.consume().value as "+" | "-";
      left = { type: "binary", op, left, right: this.term() };
    }
    return left;
  }

  term(): FormulaAST {
    let left = this.factor();
    while (
      this.peek()?.kind === "op" &&
      (this.peek()!.value === "*" || this.peek()!.value === "/")
    ) {
      const op = this.consume().value as "*" | "/";
      left = { type: "binary", op, left, right: this.factor() };
    }
    return left;
  }

  factor(): FormulaAST {
    const t = this.peek();
    if (!t) throw new FormulaSyntaxError("unexpected end of expression");
    if (t.kind === "op" && t.value === "-") {
      this.consume();
      return { type: "unary", op: "-", operand: this.factor() };
    }
    if (t.kind === "op" && t.value === "(") {
      this.consume();
      const inner = this.expr();
      const close = this.consume();
      if (close.value !== ")") throw new FormulaSyntaxError("expected ')'");
      return inner;
    }
    if (t.kind === "number") {
      this.consume();
      return { type: "number", value: Number(t.value) };
    }
    if (t.kind === "name") {
      this.consume();
      return { type: "name", name: t.value };
    }
    throw new FormulaSyntaxError(`unexpected token ${t.value}`);
  }
}

export function parseFormula(source: string): FormulaAST {
  return new Parser(tokenize(source)).parse();
}

export function tryParseFormula(
  source: string,
): { ok: true; ast: FormulaAST } | { ok: false; error: string } {
  try {
    return { ok: true, ast: parseFormula(source) };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "parse error",
    };
  }
}
