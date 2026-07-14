import { afterEach, describe, expect, it } from "vitest";

import { MetricsCatalogPage } from "@/features/metrics/catalog/metrics-catalog-page";
import {
  cleanupAuthAndFetch,
  makeTenant,
  mockApi,
  renderWithProviders,
  seedAuth,
} from "@/test/access-test-utils";
import { waitFor, type RenderResult } from "@/test/render-browser";

const SAMPLE_ROW = {
  metric_id: "propel.merged_prs",
  name: "Merged Pull Requests",
  version: 1,
  revision: 1,
  status: "active",
  content_hash: "abc",
  visibility: "team",
  description: "Count of merged PRs",
  tags: ["flow"],
  entity: "pull_request",
  source: "standard",
  extends: null,
  params_bound: null,
  draft_pending: false,
  notices: [],
  compile_error: null,
  updated_at: null,
  enrolled: true,
};

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

describe("MetricsCatalogPage", () => {
  it("renders catalog rows and New metric for managers", async () => {
    seedAuth();
    mockApi({
      tenants: [
        makeTenant({
          permissions: ["metrics:read", "metrics:manage", "tenant:read"],
        }),
      ],
      extraHandlers: [
        {
          method: "GET",
          match: /\/metric-definitions$/,
          response: [SAMPLE_ROW],
        },
      ],
    });

    result = renderWithProviders(<MetricsCatalogPage />);
    await waitFor(() =>
      Boolean(result?.container.textContent?.includes("Merged Pull Requests")),
    );
    expect(result?.container.textContent).toContain("propel.merged_prs");
    expect(result?.container.textContent).toContain("New metric");
    expect(
      result?.container.querySelector('[data-testid="metrics-table"]'),
    ).toBeTruthy();
  });

  it("hides New metric without metrics:manage", async () => {
    seedAuth();
    mockApi({
      tenants: [makeTenant({ role: "individual", permissions: ["metrics:read"] })],
      extraHandlers: [
        {
          method: "GET",
          match: /\/metric-definitions$/,
          response: [],
        },
      ],
    });

    result = renderWithProviders(<MetricsCatalogPage />);
    await waitFor(() =>
      Boolean(result?.container.querySelector('[data-testid="metrics-empty"]')),
    );
    expect(result?.container.textContent).not.toContain("New metric");
  });
});
