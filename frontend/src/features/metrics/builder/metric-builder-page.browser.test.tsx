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
    expect(result?.container.textContent).toContain("Choose a core metric");
    expect(result?.container.textContent).toContain("Basics");
    expect(result?.container.textContent).toContain("Time");
    expect(result?.container.textContent).toContain("Visibility");
    expect(result?.container.textContent).toContain("Advanced");
    expect(result?.container.textContent).not.toContain("Filters");
    expect(result?.container.textContent).toContain("Save & publish");
    await waitFor(() =>
      Boolean(result?.container.querySelector('[data-testid="preview-panel"]')),
    );
  });

  it("applies a core metric template on click", async () => {
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

    result = renderWithProviders(
      <Routes>
        <Route path="/" element={<MetricBuilderPage mode="create" />} />
      </Routes>,
    );

    await waitFor(() =>
      Boolean(result?.container.textContent?.includes("Merged pull requests")),
    );
    const card = Array.from(result!.container.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Merged pull requests"),
    );
    card!.click();
    await waitFor(() => {
      const name = result?.container.querySelector<HTMLInputElement>("#metric-name");
      return name?.value === "Merged pull requests";
    });

    // Identifier derives from the name and hides the org namespace.
    const idDisplay = result!.container.querySelector(
      '[data-testid="metric-id-display"]',
    );
    expect(idDisplay?.textContent).toBe("merged_pull_requests");
    expect(idDisplay?.textContent).not.toContain("acme.");

    // Typing a name keeps the identifier in sync (still namespace-hidden).
    const nameInput =
      result!.container.querySelector<HTMLInputElement>("#metric-name")!;
    const setValue = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value",
    )!.set!;
    setValue.call(nameInput, "My Cool Metric");
    nameInput.dispatchEvent(new Event("input", { bubbles: true }));
    await waitFor(() => {
      const display = result?.container.querySelector(
        '[data-testid="metric-id-display"]',
      );
      return display?.textContent === "my_cool_metric";
    });
  });
});
