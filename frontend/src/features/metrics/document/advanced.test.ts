import { describe, expect, it } from "vitest";

import {
  isAdvancedDocument,
  parseYamlLoose,
} from "@/features/metrics/document/advanced";

describe("isAdvancedDocument", () => {
  it("flags metadata.advanced", () => {
    expect(isAdvancedDocument({ metadata: { advanced: true } })).toBe(true);
  });

  it("flags measure.type sql", () => {
    expect(
      isAdvancedDocument({ spec: { measure: { type: "sql", sql: "select 1" } } }),
    ).toBe(true);
  });

  it("flags sql filter nodes", () => {
    expect(
      isAdvancedDocument({
        spec: { filters: [{ sql: "repo like 'acme/%'" }] },
      }),
    ).toBe(true);
  });

  it("allows simple metrics", () => {
    expect(
      isAdvancedDocument({
        metadata: { advanced: false },
        spec: {
          measure: { type: "count" },
          filters: [{ field: "state", op: "eq", value: "merged" }],
        },
      }),
    ).toBe(false);
  });
});

describe("parseYamlLoose", () => {
  it("detects advanced marker", () => {
    const doc = parseYamlLoose("metadata:\n  advanced: true\n");
    expect(doc && isAdvancedDocument(doc as never)).toBe(true);
  });
});
