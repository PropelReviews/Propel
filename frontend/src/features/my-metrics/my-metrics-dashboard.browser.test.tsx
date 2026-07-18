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

import { MyMetricsDashboard } from "./my-metrics-dashboard";
import { myMetricsStorageKey } from "./use-my-metrics-layout";
import { WIDGET_CATALOG } from "./widget-catalog";

const STORAGE_KEY = myMetricsStorageKey(TEST_USER.id, "tenant-1");

const EMPTY_SERIES = { granularity: "daily", points: [] };

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

function mountDashboard(user = TEST_USER) {
  seedAuth();
  mockApi({
    user,
    tenants: [makeTenant({ role: "individual", permissions: ["metrics:read"] })],
    extraHandlers: [
      {
        match: /\/metrics\/(pull-requests|cycle-time|review-latency|change-failure)$/,
        response: EMPTY_SERIES,
      },
    ],
  });
  result = renderWithProviders(
    <MyMetricsDashboard userId={TEST_USER.id} tenantId="tenant-1" />,
  );
  return result.container;
}

function sections(container: HTMLElement): string[] {
  return [...container.querySelectorAll("section[aria-label]")].map(
    (s) => s.getAttribute("aria-label")!,
  );
}

function findButton(root: ParentNode, text: string): HTMLButtonElement | undefined {
  return [...root.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.textContent === text || b.getAttribute("aria-label") === text,
  );
}

describe("MyMetricsDashboard", () => {
  it("renders every default chart section on first visit", async () => {
    const container = mountDashboard();
    await waitFor(() => sections(container).length === WIDGET_CATALOG.length);

    expect(sections(container)).toEqual(WIDGET_CATALOG.map((w) => w.title));
    // Everything is already visible, so there is nothing left to add.
    expect(findButton(container, "Add chart")!.disabled).toBe(true);
  });

  it("shows the GitHub connect prompt only while unlinked", async () => {
    const container = mountDashboard();
    await waitFor(() => sections(container).length > 0);
    expect(container.textContent).toContain("Connect GitHub to see your metrics");

    result?.unmount();
    cleanupAuthAndFetch();

    const linked = mountDashboard({
      ...TEST_USER,
      github: {
        connected: true,
        account_id: "1",
        account_email: null,
        login: "sam-self",
      },
    });
    // The prompt clears once /auth/me resolves with a linked GitHub login.
    await waitFor(
      () =>
        sections(linked).length === WIDGET_CATALOG.length &&
        !linked.textContent!.includes("Connect GitHub to see your metrics"),
    );
  });

  it("removes a chart and persists the choice", async () => {
    const container = mountDashboard();
    await waitFor(() => sections(container).length === WIDGET_CATALOG.length);

    await userEvent.click(findButton(container, "Remove Pull request activity")!);
    await waitFor(() => sections(container).length === WIDGET_CATALOG.length - 1);

    expect(sections(container)).not.toContain("Pull request activity");
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual([
      "cycle-time",
      "review-latency",
      "change-failure",
    ]);

    // A fresh mount for the same user + workspace keeps the saved layout.
    result?.unmount();
    const remounted = renderWithProviders(
      <MyMetricsDashboard userId={TEST_USER.id} tenantId="tenant-1" />,
    );
    result = remounted;
    await waitFor(
      () =>
        sections(remounted.container as HTMLElement).length ===
        WIDGET_CATALOG.length - 1,
    );
    expect(sections(remounted.container as HTMLElement)).not.toContain(
      "Pull request activity",
    );
  });

  it("adds a removed chart back through the Add chart dialog", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(["cycle-time"]));
    const container = mountDashboard();
    await waitFor(() => sections(container).length === 1);

    await userEvent.click(findButton(container, "Add chart")!);
    await waitFor(
      () =>
        document.body
          .querySelector('[data-slot="dialog-content"]')
          ?.textContent?.includes("Add a chart") ?? false,
    );

    const dialog = document.body.querySelector('[data-slot="dialog-content"]')!;
    // Only charts not already on the dashboard are offered.
    expect(dialog.textContent).not.toContain("Cycle time");
    const row = [...dialog.querySelectorAll("li")].find((li) =>
      li.textContent!.includes("Change failure rate"),
    )!;
    await userEvent.click(findButton(row, "Add")!);

    await waitFor(() => sections(container).includes("Change failure rate"));
    // Added charts append to the end of the layout.
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual([
      "cycle-time",
      "change-failure",
    ]);
  });

  it("shows an empty state and resets to defaults", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([]));
    const container = mountDashboard();
    await waitFor(() => container.textContent!.includes("No charts on your dashboard"));
    expect(sections(container)).toEqual([]);

    await userEvent.click(findButton(container, "Reset to defaults")!);
    await waitFor(() => sections(container).length === WIDGET_CATALOG.length);
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(
      WIDGET_CATALOG.map((w) => w.id),
    );
  });
});
