import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { MetricsSection } from "./metrics-section";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("MetricsSection", () => {
  it("renders metric cards, chart widgets, and the closer", async () => {
    result = renderInDom(<MetricsSection />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Defaults, not limits"));

    expect(container.textContent).toContain("Cycle time");
    expect(container.textContent).toContain("Throughput");
    expect(container.textContent).toContain("Review latency");
    expect(container.textContent).toContain("Rework rate");
    expect(container.textContent).toContain("PR activity by team");
    expect(container.textContent).toContain("Deploys");
    expect(container.textContent).toContain(
      "Each one editable. None of them the ceiling.",
    );

    await waitFor(() => container.querySelector("svg.recharts-surface") !== null);
    expect(
      container.querySelectorAll('[data-slot="chart-widget"]').length,
    ).toBeGreaterThan(0);
  });
});
