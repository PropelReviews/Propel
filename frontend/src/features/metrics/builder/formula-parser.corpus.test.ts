/**
 * Shared corpus with Python propel_metrics.expr — ok/error flags must match.
 * AST shape for successful parses is asserted for a few golden expressions.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  parseFormula,
  tryParseFormula,
} from "@/features/metrics/builder/formula-parser";

const CORPUS = join(
  process.cwd(),
  "..",
  "transformation",
  "propel_metrics",
  "tests",
  "fixtures",
  "formula_corpus.json",
);

describe("formula corpus parity with Python fixtures", () => {
  const cases = JSON.parse(readFileSync(CORPUS, "utf8")) as Array<{
    expr: string;
    ok: boolean;
  }>;

  for (const c of cases) {
    it(`${JSON.stringify(c.expr)} ok=${c.ok}`, () => {
      const result = tryParseFormula(c.expr);
      expect(result.ok).toBe(c.ok);
    });
  }

  it("matches expected AST for a + b / c", () => {
    expect(parseFormula("a + b / c")).toEqual({
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
});
