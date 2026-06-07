import type { Meta, StoryObj } from "@storybook/react-vite";

import {
  cycleTimeSeries,
  deploySeries,
  mockCycleTimeSeries,
  mockDeploySeries,
  mockMetricSummaries,
  mockTeamComparisonData,
  mockThroughputSeries,
  teamActivitySeries,
  throughputSeries,
} from "@/lib/mock-metrics";

import { AreaChartWidget } from "./area-chart-widget";
import { BarChartWidget } from "./bar-chart-widget";
import { formatCount, formatDuration, formatWeekLabel } from "./formatters";
import { LineChartWidget } from "./line-chart-widget";
import { MetricCard } from "./metric-card";

function Gallery() {
  return (
    <div className="flex flex-col gap-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {mockMetricSummaries.map((summary) => (
          <MetricCard
            key={summary.metric}
            label={summary.metric}
            value={
              summary.unit === "hours"
                ? formatDuration(summary.value)
                : summary.unit === "percent"
                  ? `${summary.value}%`
                  : formatCount(summary.value)
            }
            delta={summary.deltaPercent}
            higherIsBetter={summary.higherIsBetter}
          />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <LineChartWidget
          title="Cycle time trend"
          description="Median hours from first commit to merge"
          footer="Last 12 weeks"
          data={mockCycleTimeSeries}
          series={cycleTimeSeries}
          xFormatter={formatWeekLabel}
          valueFormatter={formatDuration}
        />
        <LineChartWidget
          title="Throughput"
          description="Pull requests merged per week"
          footer="Last 12 weeks"
          data={mockThroughputSeries}
          series={throughputSeries}
          xFormatter={formatWeekLabel}
          valueFormatter={formatCount}
        />
        <BarChartWidget
          title="PR activity by team"
          description="Opened vs. merged in the current cycle"
          data={mockTeamComparisonData}
          series={teamActivitySeries}
          xKey="category"
          valueFormatter={formatCount}
        />
        <AreaChartWidget
          title="Deploys"
          description="Production deploys per week"
          footer="Last 12 weeks"
          data={mockDeploySeries}
          series={deploySeries}
          xFormatter={formatWeekLabel}
          valueFormatter={formatCount}
        />
      </div>
    </div>
  );
}

const meta = {
  title: "Charts/Gallery",
  component: Gallery,
} satisfies Meta<typeof Gallery>;

export default meta;
type Story = StoryObj<typeof meta>;

export const AllWidgets: Story = {};
