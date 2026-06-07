import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor } from "@/test/render-browser";

import { MetricCard } from "./metric-card";

const sparkline = [{ value: 30 }, { value: 27 }, { value: 25 }, { value: 18 }];

let result: ReturnType<typeof renderInDom> | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("MetricCard", () => {
  it("renders the label, value, and delta", async () => {
    result = renderInDom(
      <MetricCard label="Median cycle time" value="18.4h" delta={-12.3} />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Median cycle time"));
    expect(container.textContent).toContain("18.4h");
    expect(container.textContent).toContain("-12.3%");
  });

  it("renders a sparkline SVG when sparkline data is provided", async () => {
    result = renderInDom(
      <MetricCard label="Cycle time" value="18.4h" sparklineData={sparkline} />,
    );
    const { container } = result;

    await waitFor(() => container.querySelectorAll(".recharts-line").length === 1);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("omits the delta badge when delta is zero or undefined", async () => {
    result = renderInDom(<MetricCard label="Open PRs" value="14" />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Open PRs"));
    expect(container.querySelector('[data-slot="badge"]')).toBeNull();
  });
});
