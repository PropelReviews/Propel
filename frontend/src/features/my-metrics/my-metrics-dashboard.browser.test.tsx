import { afterEach, describe, expect, it } from "vitest";
import { userEvent } from "vitest/browser";

import {
  cleanupAuthAndFetch,
  makeTenant,
  mockApi,
  renderWithProviders,
  seedAuth,
  TEST_USER,
} from "@/test/access-test-utils";
import { waitFor, type RenderResult } from "@/test/render-browser";

import { myMetricsStorageKey } from "./dashboard-layout";
import { MyMetricsDashboard } from "./my-metrics-dashboard";

const STORAGE_KEY = myMetricsStorageKey(TEST_USER.id, "tenant-1");
const EMPTY_SERIES = {
  metric_id: "propel.cycle_time",
  granularity: "weekly",
  unit: "duration",
  format: "humanize_duration",
  points: [],
};

const CATALOG = [
  {
    metric_id: "propel.cycle_time",
    name: "PR Cycle Time",
    version: 1,
    revision: 1,
    status: "active",
    content_hash: "abc",
    visibility: "ic",
    description: "Median time from PR open to merge.",
    tags: ["dora"],
    entity: "pull_request",
    source: "standard",
    extends: null,
    params_bound: null,
    draft_pending: false,
    notices: [],
    compile_error: null,
    updated_at: null,
    enrolled: true,
    display: {
      unit: "duration",
      format: "humanize_duration",
      direction: "lower_is_better",
    },
    grains: ["day", "week", "month"],
  },
  {
    metric_id: "propel.merged_prs",
    name: "Merged PRs",
    version: 1,
    revision: 1,
    status: "active",
    content_hash: "def",
    visibility: "team",
    description: "Count of merged pull requests.",
    tags: [],
    entity: "pull_request",
    source: "standard",
    extends: null,
    params_bound: null,
    draft_pending: false,
    notices: [],
    compile_error: null,
    updated_at: null,
    enrolled: true,
    display: { unit: "count", format: null, direction: null },
    grains: ["day", "week", "month"],
  },
  {
    metric_id: "propel.change_failure_rate",
    name: "Change Failure Rate",
    version: 1,
    revision: 1,
    status: "active",
    content_hash: "ghi",
    visibility: "org",
    description: "Share of merges that look like reverts.",
    tags: ["dora"],
    entity: null,
    source: "standard",
    extends: null,
    params_bound: null,
    draft_pending: false,
    notices: [],
    compile_error: null,
    updated_at: null,
    enrolled: true,
    display: {
      unit: "percent",
      format: "percent_1dp",
      direction: "lower_is_better",
    },
    grains: ["day", "week", "month"],
  },
];

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

function baseHandlers(
  overrides: Array<{
    method?: string;
    match: RegExp;
    response: unknown | (() => unknown);
    status?: number;
  }> = [],
) {
  return [
    {
      match: /\/metric-definitions(\?|$)/,
      response: CATALOG,
    },
    {
      match: /\/metrics\/values\?/,
      response: EMPTY_SERIES,
    },
    {
      method: "GET",
      match: /\/dashboard-preference$/,
      status: 404,
      response: { detail: "No dashboard preference saved" },
    },
    {
      method: "PUT",
      match: /\/dashboard-preference$/,
      response: {
        layout: { version: 2, tiles: [] },
        updated_at: new Date().toISOString(),
      },
    },
    ...overrides,
  ];
}

function mountDashboard(
  handlers = baseHandlers(),
  user = {
    ...TEST_USER,
    github: {
      connected: true,
      account_id: "1",
      account_email: null,
      login: "sam-self",
    },
  },
) {
  seedAuth();
  mockApi({
    user,
    tenants: [makeTenant({ role: "individual", permissions: ["metrics:read"] })],
    extraHandlers: handlers,
  });
  result = renderWithProviders(
    <MyMetricsDashboard userId={TEST_USER.id} tenantId="tenant-1" />,
  );
  return result.container;
}

function tileLabels(container: HTMLElement): string[] {
  return [...container.querySelectorAll("[data-testid^='dashboard-tile-']")].map(
    (el) => el.getAttribute("aria-label") ?? "",
  );
}

function findButton(root: ParentNode, text: string): HTMLButtonElement | undefined {
  return [...root.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.textContent === text || b.getAttribute("aria-label") === text,
  );
}

describe("MyMetricsDashboard", () => {
  it("renders default preferred metrics from the catalog", async () => {
    const container = mountDashboard();
    await waitFor(() => tileLabels(container).includes("PR Cycle Time"));

    const labels = tileLabels(container);
    expect(labels).toContain("PR Cycle Time");
    expect(labels).toContain("Merged PRs");
    expect(labels).toContain("Change Failure Rate");
    expect(container.querySelector("[data-slot='metric-filters-bar']")).toBeTruthy();
  });

  it("removes a chart and persists the choice locally", async () => {
    const container = mountDashboard();
    await waitFor(() => tileLabels(container).includes("PR Cycle Time"));

    await userEvent.click(findButton(container, "Remove PR Cycle Time")!);
    await waitFor(() => !tileLabels(container).includes("PR Cycle Time"));

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(stored.version).toBe(2);
    expect(stored.tiles.map((t: { i: string }) => t.i)).not.toContain(
      "propel.cycle_time",
    );
  });

  it("adds a removed chart back through the Add chart dialog", async () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        version: 2,
        range: "quarter",
        granularity: "weekly",
        tiles: [{ i: "propel.cycle_time", x: 0, y: 0, w: 6, h: 4 }],
      }),
    );
    const container = mountDashboard();
    await waitFor(() => tileLabels(container).length === 1);

    await userEvent.click(findButton(container, "Add chart")!);
    await waitFor(
      () =>
        document.body
          .querySelector('[data-slot="dialog-content"]')
          ?.textContent?.includes("Add a chart") ?? false,
    );

    const dialog = document.body.querySelector('[data-slot="dialog-content"]')!;
    expect(dialog.textContent).not.toContain("PR Cycle Time");
    const row = [...dialog.querySelectorAll("li")].find((li) =>
      li.textContent!.includes("Change Failure Rate"),
    )!;
    await userEvent.click(findButton(row, "Add")!);

    await waitFor(() => tileLabels(container).includes("Change Failure Rate"));
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(stored.tiles.map((t: { i: string }) => t.i)).toEqual([
      "propel.cycle_time",
      "propel.change_failure_rate",
    ]);
  });

  it("shows an empty state and resets to defaults", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 2, tiles: [] }));
    const container = mountDashboard();
    await waitFor(() => container.textContent!.includes("No charts on your dashboard"));
    expect(tileLabels(container)).toEqual([]);

    await userEvent.click(findButton(container, "Reset to defaults")!);
    await waitFor(() => tileLabels(container).includes("PR Cycle Time"));
  });

  it("restores from the server when local storage is empty", async () => {
    const container = mountDashboard([
      {
        match: /\/metric-definitions(\?|$)/,
        response: CATALOG,
      },
      {
        match: /\/metrics\/values\?/,
        response: EMPTY_SERIES,
      },
      {
        method: "GET",
        match: /\/dashboard-preference$/,
        response: {
          layout: {
            version: 2,
            range: "month",
            granularity: "daily",
            tiles: [{ i: "propel.merged_prs", x: 0, y: 0, w: 12, h: 4 }],
          },
          updated_at: "2026-07-18T00:00:00Z",
        },
      },
      {
        method: "PUT",
        match: /\/dashboard-preference$/,
        response: {
          layout: { version: 2, tiles: [] },
          updated_at: "2026-07-18T00:00:00Z",
        },
      },
    ]);
    await waitFor(() => tileLabels(container).includes("Merged PRs"));
    expect(tileLabels(container)).toEqual(["Merged PRs"]);
  });
});
