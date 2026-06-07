import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor } from "@/test/render-browser";

import { AreaChartWidget } from "./area-chart-widget";
import type { ChartSeries, TimeSeriesPoint } from "./types";

const data: TimeSeriesPoint[] = [
  { date: "2026-04-06", value: 18 },
  { date: "2026-04-13", value: 21 },
  { date: "2026-04-20", value: 19 },
  { date: "2026-04-27", value: 24 },
];

const series: ChartSeries[] = [{ key: "value", label: "Deploys" }];

let result: ReturnType<typeof renderInDom> | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("AreaChartWidget", () => {
  it("renders the title and an area in an SVG", async () => {
    result = renderInDom(
      <AreaChartWidget title="Deploys" data={data} series={series} />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Deploys"));
    await waitFor(() => container.querySelectorAll(".recharts-area").length === 1);
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("shows the empty message when there is no data", async () => {
    result = renderInDom(
      <AreaChartWidget
        title="Deploys"
        data={[]}
        series={series}
        emptyMessage="No deploy data"
      />,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("No deploy data"));
    expect(container.querySelector("svg")).toBeNull();
  });
});
