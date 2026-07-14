import { describe, expect, it } from "vitest";

import {
  fieldForPath,
  validateMetricDocument,
} from "@/features/metrics/schema/client-validate";
import { emptyMetricDocument } from "@/features/metrics/document/store";

describe("validateMetricDocument", () => {
  it("accepts a minimal valid count metric", () => {
    const doc = emptyMetricDocument("acme.sample", "Sample");
    const issues = validateMetricDocument(doc);
    expect(issues.filter((i) => i.source === "schema")).toEqual([]);
  });

  it("flags missing required metadata.name via schema", () => {
    const doc = emptyMetricDocument("acme.sample", "Sample");
    delete (doc.metadata as Record<string, unknown>).name;
    const issues = validateMetricDocument(doc);
    expect(issues.some((i) => i.code === "E_SCHEMA")).toBe(true);
  });

  it("flags incompatible filter ops via semantic mirror", () => {
    const doc = emptyMetricDocument("acme.sample", "Sample");
    (doc.spec as Record<string, unknown>).filters = [
      { field: "state", op: "contains", value: "x" },
    ];
    const issues = validateMetricDocument(doc, {
      entities: [
        {
          name: "pull_request",
          fields: [{ name: "state", type: "enum", role: "dimension" }],
        },
      ],
    });
    expect(issues.some((i) => i.code === "E_OP_TYPE")).toBe(true);
  });
});

describe("fieldForPath", () => {
  it("maps filter paths to the filters section", () => {
    expect(fieldForPath("$.spec.filters[0].op")).toBe("filters");
  });
});
