import { describe, expect, it } from "vitest";

import { summarizeFilters } from "@/features/metrics/builder/filter-summary";

describe("summarizeFilters", () => {
  it("summarizes predicates", () => {
    expect(
      summarizeFilters([
        { field: "state", op: "eq", value: "merged" },
        { field: "repo", op: "starts_with", value: "acme/" },
      ]),
    ).toContain("state = `merged`");
  });

  it("never throws on empty", () => {
    expect(summarizeFilters([])).toBe("No filters");
  });

  it("handles groups", () => {
    const text = summarizeFilters([
      {
        any_of: [
          { field: "repo", op: "eq", value: "a" },
          { field: "repo", op: "eq", value: "b" },
        ],
      },
    ]);
    expect(text).toContain("or");
  });
});
