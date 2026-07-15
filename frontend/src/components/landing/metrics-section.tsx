import {
  AreaChartWidget,
  BarChartWidget,
  formatCount,
  formatDuration,
  formatPercent,
  formatWeekLabel,
  LineChartWidget,
  MetricCard,
  MetricFiltersBar,
  MetricFiltersProvider,
  useResampledSeries,
} from "@/components/charts";
import { Section } from "@/components/ui/section";
import { SectionHeading } from "@/components/ui/section-heading";
import {
  cycleTimeSeries,
  deploySeries,
  mockDailyCycleTime,
  mockDailyDeploys,
  mockDailyThroughput,
  mockTeamComparisonData,
  teamActivitySeries,
  throughputSeries,
} from "@/lib/mock-metrics";

const headlineMetrics = [
  {
    label: "Cycle time",
    value: formatDuration(18.4),
    delta: -12.3,
    higherIsBetter: false,
  },
  {
    label: "Throughput",
    value: formatCount(72),
    delta: 8.1,
    higherIsBetter: true,
  },
  {
    label: "Review latency",
    value: formatDuration(6.2),
    delta: -9.4,
    higherIsBetter: false,
  },
  {
    label: "Rework rate",
    value: formatPercent(14),
    delta: -3.1,
    higherIsBetter: false,
  },
] as const;

function LinkedDemoCharts() {
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
        description="Median hours to merge"
        data={cycleTime}
        series={cycleTimeSeries}
        xFormatter={formatWeekLabel}
        valueFormatter={formatDuration}
      />
      <LineChartWidget
        title="Throughput"
        description="Pull requests merged"
        data={throughput}
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
        description="Production deploys"
        data={deploys}
        series={deploySeries}
        xFormatter={formatWeekLabel}
        valueFormatter={formatCount}
      />
    </div>
  );
}

export function MetricsSection() {
  return (
    <Section id="metrics">
      <SectionHeading
        title="Defaults, not limits"
        description="The same chart widgets the product ships. Change the range — every chart updates."
      />

      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {headlineMetrics.map((metric) => (
          <MetricCard
            key={metric.label}
            label={metric.label}
            value={metric.value}
            delta={metric.delta}
            higherIsBetter={metric.higherIsBetter}
          />
        ))}
      </div>

      <MetricFiltersProvider initialRange="quarter">
        <div className="mt-8 mb-4">
          <MetricFiltersBar />
        </div>
        <LinkedDemoCharts />
      </MetricFiltersProvider>

      <p className="text-foreground mx-auto mt-10 max-w-2xl text-center text-base font-medium text-balance">
        Each one editable. None of them the ceiling.
      </p>
    </Section>
  );
}
