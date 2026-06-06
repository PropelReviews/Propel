import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  cycleTimeSeries,
  deploySeries,
  mockDailyCycleTime,
  mockDailyDeploys,
  mockDailyThroughput,
  throughputSeries,
} from "@/lib/mock-metrics";

import { AreaChartWidget } from "../area-chart-widget";
import { formatCount, formatDuration, formatWeekLabel } from "../formatters";
import { LineChartWidget } from "../line-chart-widget";
import { MetricFiltersBar } from "./metric-filters-bar";
import { MetricFiltersProvider } from "./metric-filters-context";
import { useResampledSeries } from "./use-resampled-series";

function LinkedCharts() {
  const cycleTime = useResampledSeries(mockDailyCycleTime, {
    how: "avg",
    valueKey: "median",
  });
  const throughput = useResampledSeries(mockDailyThroughput, { how: "sum" });
  const deploys = useResampledSeries(mockDailyDeploys, { how: "sum" });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <LineChartWidget
        title="Cycle time"
        data={cycleTime}
        series={cycleTimeSeries}
        xFormatter={formatWeekLabel}
        valueFormatter={formatDuration}
      />
      <LineChartWidget
        title="Throughput"
        data={throughput}
        series={throughputSeries}
        xFormatter={formatWeekLabel}
        valueFormatter={formatCount}
      />
      <AreaChartWidget
        title="Deploys"
        data={deploys}
        series={deploySeries}
        xFormatter={formatWeekLabel}
        valueFormatter={formatCount}
      />
    </div>
  );
}

function Demo() {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="flex flex-col gap-4">
        <MetricFiltersBar />
        <LinkedCharts />
      </div>
    </MetricFiltersProvider>
  );
}

const meta = {
  title: "Charts/Filters/MetricFiltersBar",
  component: Demo,
} satisfies Meta<typeof Demo>;

export default meta;
type Story = StoryObj<typeof meta>;

/** One picker drives every chart. Change the range or granularity to resample. */
export const LinkedDashboard: Story = {};
