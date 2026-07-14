import { afterEach, describe, expect, it } from "vitest";
import { Route, Routes } from "react-router-dom";

import { MetricBuilderPage } from "@/features/metrics/builder/metric-builder-page";
import {
  cleanupAuthAndFetch,
  makeTenant,
  mockApi,
  renderWithProviders,
  seedAuth,
} from "@/test/access-test-utils";
import { waitFor, type RenderResult } from "@/test/render-browser";

const CATALOG = {
  catalog_version: 1,
  cardinality: { warn_above: 500, error_above: 5000 },
  entities: [
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
          name: "merged_at",
          type: "timestamp",
          role: "event_time",
          values: null,
          nullable: true,
          cardinality_estimate: null,
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
  ],
  virtual_dimensions: [],
};

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

describe("MetricBuilderPage golden create flow (mocked)", () => {
  it("renders builder sections for a new metric", async () => {
    seedAuth();
    mockApi({
      tenants: [
        makeTenant({
          slug: "acme",
          permissions: ["metrics:read", "metrics:manage", "tenant:read"],
        }),
      ],
      extraHandlers: [
        {
          method: "GET",
          match: /\/metric-catalog$/,
          response: CATALOG,
        },
        {
          method: "POST",
          match: /metric-definitions:validate$/,
          response: { ok: true, errors: [], warnings: [] },
        },
      ],
    });

    // useSearchParams needs a route match
    result = renderWithProviders(
      <Routes>
        <Route path="/" element={<MetricBuilderPage mode="create" />} />
      </Routes>,
    );

    await waitFor(() => Boolean(result?.container.textContent?.includes("New metric")));
    expect(result?.container.textContent).toContain("Basics");
    expect(result?.container.textContent).toContain("Filters");
    expect(result?.container.textContent).toContain("Display & visibility");
    expect(result?.container.textContent).toContain("Activate");
    await waitFor(() =>
      Boolean(result?.container.querySelector('[data-testid="preview-panel"]')),
    );
  });
});
