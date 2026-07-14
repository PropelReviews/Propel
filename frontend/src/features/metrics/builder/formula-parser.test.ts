import { describe, expect, it } from "vitest";

import {
  FormulaSyntaxError,
  parseFormula,
  tryParseFormula,
} from "@/features/metrics/builder/formula-parser";

describe("parseFormula", () => {
  it("parses a + b / c", () => {
    const ast = parseFormula("a + b / c");
    expect(ast).toEqual({
      type: "binary",
      op: "+",
      left: { type: "name", name: "a" },
      right: {
        type: "binary",
        op: "/",
        left: { type: "name", name: "b" },
        right: { type: "name", name: "c" },
      },
    });
  });

  it("parses parentheses and unary minus", () => {
    const ast = parseFormula("-(a + 2)");
    expect(ast.type).toBe("unary");
  });

  it("rejects bad tokens", () => {
    expect(() => parseFormula("a +")).toThrow(FormulaSyntaxError);
    expect(tryParseFormula("a $ b").ok).toBe(false);
  });
});
