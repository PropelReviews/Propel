import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor } from "@/test/render-browser";

import { BarChartWidget } from "./bar-chart-widget";
import type { CategoryPoint, ChartSeries } from "./types";

const data: CategoryPoint[] = [
  { category: "Platform", opened: 38, merged: 34 },
  { category: "Growth", opened: 29, merged: 25 },
  { category: "Payments", opened: 22, merged: 21 },
];

const series: ChartSeries[] = [
  { key: "opened", label: "Opened" },
  { key: "merged", label: "Merged" },
];

let result: ReturnType<typeof renderInDom> | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("BarChartWidget", () => {
  it("renders a bar series per series key", async () => {
    result = renderInDom(
      <BarChartWidget
        title="PR activity"
        data={data}
        series={series}
        xKey="category"
      />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("PR activity"));
    await waitFor(() => container.querySelectorAll(".recharts-bar").length === 2);
    // 3 categories x 2 series = 6 rectangles
    await waitFor(
      () => container.querySelectorAll(".recharts-bar-rectangle").length === 6,
    );
  });

  it("shows the empty message when there is no data", async () => {
    result = renderInDom(
      <BarChartWidget
        title="PR activity"
        data={[]}
        series={series}
        xKey="category"
        emptyMessage="No team activity yet"
      />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("No team activity yet"));
    expect(container.querySelector("svg")).toBeNull();
  });
});
