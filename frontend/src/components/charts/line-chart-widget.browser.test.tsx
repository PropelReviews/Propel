import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor } from "@/test/render-browser";

import { LineChartWidget } from "./line-chart-widget";
import type { ChartSeries, TimeSeriesPoint } from "./types";

const data: TimeSeriesPoint[] = [
  { date: "2026-04-06", median: 27.5, p90: 44.2 },
  { date: "2026-04-13", median: 25.9, p90: 41.8 },
  { date: "2026-04-20", median: 23.1, p90: 38.4 },
  { date: "2026-04-27", median: 21.8, p90: 35.1 },
];

const single: ChartSeries[] = [{ key: "median", label: "Median" }];
const multi: ChartSeries[] = [
  { key: "median", label: "Median" },
  { key: "p90", label: "P90" },
];

let result: ReturnType<typeof renderInDom> | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("LineChartWidget", () => {
  it("renders the title and an SVG with one line per series", async () => {
    result = renderInDom(
      <LineChartWidget title="Cycle time" data={data} series={single} />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Cycle time"));
    await waitFor(() => container.querySelectorAll(".recharts-line").length === 1);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("renders one line per series for multi-series data", async () => {
    result = renderInDom(
      <LineChartWidget title="Distribution" data={data} series={multi} />,
    );
    const { container } = result;

    await waitFor(() => container.querySelectorAll(".recharts-line").length === 2);
  });

  it("shows the empty message when there is no data", async () => {
    result = renderInDom(
      <LineChartWidget
        title="Cycle time"
        data={[]}
        series={single}
        emptyMessage="No cycle time data yet"
      />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("No cycle time data yet"));
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders a skeleton when loading", async () => {
    result = renderInDom(
      <LineChartWidget title="Cycle time" data={[]} series={single} isLoading />,
    );
    const { container } = result;

    await waitFor(
      () => container.querySelector('[data-slot="chart-loading"]') !== null,
    );
    expect(container.querySelector("svg")).toBeNull();
  });
});
