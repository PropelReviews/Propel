import { describe, expect, it } from "vitest";

import {
  applyPatch,
  createDocumentState,
  documentReducer,
  emptyMetricDocument,
} from "@/features/metrics/document/store";
import {
  documentFromYaml,
  documentToYaml,
  normalizeForRoundTrip,
} from "@/features/metrics/document/yaml-io";

describe("documentReducer", () => {
  it("applies set patches and supports undo", () => {
    let state = createDocumentState(emptyMetricDocument("acme.demo"));
    state = documentReducer(state, {
      type: "patch",
      patch: { op: "set", path: ["metadata", "name"], value: "Demo" },
    });
    expect(state.doc.metadata).toMatchObject({ name: "Demo" });
    state = documentReducer(state, { type: "undo" });
    expect(state.doc.metadata).toMatchObject({ name: "New metric" });
  });

  it("sets nested filter fields", () => {
    const doc = emptyMetricDocument("acme.demo");
    const next = applyPatch(doc, {
      op: "set",
      path: ["spec", "filters"],
      value: [{ field: "state", op: "eq", value: "merged" }],
    });
    expect(next.spec).toMatchObject({
      filters: [{ field: "state", op: "eq", value: "merged" }],
    });
  });
});

describe("yaml round-trip", () => {
  it("round-trips a simple count metric", () => {
    const original = emptyMetricDocument("acme.merged_like", "Merged-like");
    (original.spec as Record<string, unknown>).filters = [
      { field: "state", op: "eq", value: "merged" },
    ];
    const yaml = documentToYaml(original);
    const parsed = documentFromYaml(yaml);
    expect(normalizeForRoundTrip(parsed)).toEqual(normalizeForRoundTrip(original));
  });
});
