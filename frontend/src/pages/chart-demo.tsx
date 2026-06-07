import {
  AreaChartWidget,
  BarChartWidget,
  formatCount,
  formatDuration,
  formatWeekLabel,
  LineChartWidget,
  MetricCard,
  MetricFiltersBar,
  MetricFiltersProvider,
  PropelLineChart,
  useResampledSeries,
} from "@/components/charts";
import {
  cycleTimeSeries,
  deploySeries,
  mockCycleTimeSeries,
  mockDailyCycleTime,
  mockDailyDeploys,
  mockDailyThroughput,
  mockDeploySeries,
  mockMetricSummaries,
  mockTeamComparisonData,
  mockThroughputSeries,
  teamActivitySeries,
  throughputSeries,
} from "@/lib/mock-metrics";

function unitFormatter(unit: string) {
  if (unit === "hours") return formatDuration;
  if (unit === "percent") return (value: number) => `${Math.round(value)}%`;
  return formatCount;
}

function formatValue(unit: string, value: number) {
  return unitFormatter(unit)(value);
}

/**
 * Visual gallery for the chart design library. Mounted at `/dev/charts`, it
 * exercises every widget and primitive with mock data so charts can be eyeballed
 * in light and dark themes. This is a development surface, not a product page.
 */
/**
 * Charts wired to the shared filters. Each one resamples its daily series to the
 * active range + granularity, so the single picker above drives all of them.
 */
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

export function ChartDemoPage() {
  return (
    <main className="bg-background mx-auto min-h-svh max-w-6xl px-6 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight">Chart library</h1>
        <p className="text-muted-foreground mt-2 max-w-2xl">
          Drop-in data visualization components built on shadcn and Recharts. Every
          chart takes typed <code>data</code> and <code>series</code> props and pulls
          its colors from the theme.
        </p>
      </header>

      <section className="mb-12">
        <h2 className="mb-4 text-lg font-medium">Headline metrics</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {mockMetricSummaries.map((summary) => (
            <MetricCard
              key={summary.metric}
              label={summary.metric}
              value={formatValue(summary.unit, summary.value)}
              delta={summary.deltaPercent}
              higherIsBetter={summary.higherIsBetter}
            />
          ))}
        </div>
      </section>

      <section className="mb-12">
        <h2 className="mb-4 text-lg font-medium">Chart widgets</h2>
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
      </section>

      <section className="mb-12">
        <h2 className="mb-1 text-lg font-medium">Bare primitives</h2>
        <p className="text-muted-foreground mb-4 text-sm">
          The same charts without a card wrapper, proving they drop into any layout.
        </p>
        <div className="rounded-xl border p-6">
          <PropelLineChart
            data={mockThroughputSeries}
            series={throughputSeries}
            xFormatter={formatWeekLabel}
            valueFormatter={formatCount}
            height={200}
          />
        </div>
      </section>

      <section className="mb-12">
        <h2 className="mb-1 text-lg font-medium">Linked dashboard</h2>
        <p className="text-muted-foreground mb-4 text-sm">
          One date range + granularity picker drives every chart below. Change a control
          and all linked charts resample together.
        </p>
        <MetricFiltersProvider initialRange="quarter">
          <div className="mb-4">
            <MetricFiltersBar />
          </div>
          <LinkedCharts />
        </MetricFiltersProvider>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-medium">States</h2>
        <div className="grid gap-4 lg:grid-cols-2">
          <LineChartWidget
            title="Loading"
            description="Skeleton placeholder while data loads"
            data={[]}
            series={cycleTimeSeries}
            isLoading
          />
          <LineChartWidget
            title="Empty"
            description="No data for the selected range"
            data={[]}
            series={cycleTimeSeries}
            emptyMessage="No cycle time data yet"
          />
        </div>
      </section>
    </main>
  );
}

export default ChartDemoPage;
