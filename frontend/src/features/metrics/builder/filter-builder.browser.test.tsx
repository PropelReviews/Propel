import { afterEach, describe, expect, it } from "vitest";

import { FilterBuilder } from "@/features/metrics/builder/filter-builder";
import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

const ENTITIES = [
  {
    name: "pull_request",
    grain: "one row per PR",
    dbt_model: "pull_request",
    fields: [
      {
        name: "state",
        type: "enum",
        role: "dimension",
        values: ["open", "merged", "closed"],
        nullable: null,
        cardinality_estimate: 3,
        person: false,
        virtual: false,
        mapping_id: null,
      },
      {
        name: "repo",
        type: "string",
        role: "dimension",
        values: null,
        nullable: null,
        cardinality_estimate: 200,
        person: false,
        virtual: false,
        mapping_id: null,
      },
    ],
  },
];

let result: RenderResult | undefined;
let filters: unknown[] = [];

afterEach(() => {
  result?.unmount();
  result = undefined;
  filters = [];
});

describe("FilterBuilder", () => {
  it("renders summary and add condition control", async () => {
    filters = [{ field: "state", op: "eq", value: "merged" }];
    result = renderInDom(
      <FilterBuilder
        entity="pull_request"
        catalogEntities={ENTITIES}
        filters={filters}
        onChange={(next) => {
          filters = next;
        }}
      />,
    );
    await waitFor(() =>
      Boolean(result?.container.querySelector('[data-testid="filter-summary"]')),
    );
    expect(result?.container.textContent).toContain("state = `merged`");
    const add = Array.from(result!.container.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Add condition"),
    );
    expect(add).toBeTruthy();
    add!.click();
    await waitFor(() => filters.length === 2);
    expect(filters.length).toBe(2);
  });
});
