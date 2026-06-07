import type {
  CategoryPoint,
  ChartSeries,
  DailyPoint,
  TimeSeriesPoint,
} from "@/components/charts";
import { startOfDay, toIsoDate } from "@/components/charts";

import type {
  MetricBreakdownResponse,
  MetricSummary,
  MetricTimeSeriesResponse,
} from "./mock-metrics.types";

// --- Adapters: API response shapes -> chart-ready data ----------------------

/**
 * Converts a metric time series into chart-ready points keyed by `date`. The
 * numeric value lives under `valueKey` (default `"value"`). Swapping the mock
 * source for the real API later only changes where the response comes from.
 */
export function toTimeSeriesData(
  response: MetricTimeSeriesResponse,
  valueKey = "value",
): TimeSeriesPoint[] {
  return response.points.map((point) => ({
    date: point.period,
    [valueKey]: point.value,
  }));
}

/** Converts a categorical breakdown into chart-ready points keyed by `category`. */
export function toBreakdownData(
  response: MetricBreakdownResponse,
): CategoryPoint[] {
  return response.rows.map((row) => ({ category: row.category, ...row.values }));
}

// --- Fixtures ---------------------------------------------------------------

const WEEK_STARTS = [
  "2026-03-16",
  "2026-03-23",
  "2026-03-30",
  "2026-04-06",
  "2026-04-13",
  "2026-04-20",
  "2026-04-27",
  "2026-05-04",
  "2026-05-11",
  "2026-05-18",
  "2026-05-25",
  "2026-06-01",
];

function weekly(values: number[]): MetricTimeSeriesResponse["points"] {
  return values.map((value, index) => ({ period: WEEK_STARTS[index], value }));
}

/** Median hours from first commit to merge, by week. Lower is better. */
export const mockCycleTime: MetricTimeSeriesResponse = {
  metric: "cycle_time_hours",
  unit: "hours",
  points: weekly([
    32.4, 29.1, 30.8, 27.5, 25.9, 26.4, 23.1, 21.8, 22.6, 19.4, 18.9, 18.4,
  ]),
};

/** Pull requests merged per week. Higher is better. */
export const mockThroughput: MetricTimeSeriesResponse = {
  metric: "prs_merged",
  unit: "count",
  points: weekly([42, 38, 45, 51, 47, 53, 58, 61, 55, 64, 69, 72]),
};

/** Cumulative deploys per week. */
export const mockDeploys: MetricTimeSeriesResponse = {
  metric: "deploys",
  unit: "count",
  points: weekly([12, 14, 11, 18, 21, 19, 24, 28, 26, 31, 35, 38]),
};

/** PRs opened vs. merged, broken down by team. */
export const mockTeamComparison: MetricBreakdownResponse = {
  metric: "pr_activity",
  unit: "count",
  seriesKeys: ["opened", "merged"],
  rows: [
    { category: "Platform", values: { opened: 38, merged: 34 } },
    { category: "Growth", values: { opened: 29, merged: 25 } },
    { category: "Payments", values: { opened: 22, merged: 21 } },
    { category: "Mobile", values: { opened: 31, merged: 27 } },
    { category: "Data", values: { opened: 18, merged: 16 } },
  ],
};

/** Headline KPIs for the metric cards. */
export const mockMetricSummaries: MetricSummary[] = [
  {
    metric: "Median cycle time",
    unit: "hours",
    value: 18.4,
    deltaPercent: -12.3,
    higherIsBetter: false,
  },
  {
    metric: "PRs merged",
    unit: "count",
    value: 72,
    deltaPercent: 8.1,
    higherIsBetter: true,
  },
  {
    metric: "Review coverage",
    unit: "percent",
    value: 94,
    deltaPercent: 2.4,
    higherIsBetter: true,
  },
  {
    metric: "Deploys",
    unit: "count",
    value: 38,
    deltaPercent: 9.6,
    higherIsBetter: true,
  },
];

// --- Pre-derived chart data + series definitions ----------------------------

export const mockCycleTimeSeries: TimeSeriesPoint[] = toTimeSeriesData(
  mockCycleTime,
  "median",
);

export const mockThroughputSeries: TimeSeriesPoint[] =
  toTimeSeriesData(mockThroughput);

export const mockDeploySeries: TimeSeriesPoint[] = toTimeSeriesData(mockDeploys);

export const mockTeamComparisonData: CategoryPoint[] =
  toBreakdownData(mockTeamComparison);

export const cycleTimeSeries: ChartSeries[] = [
  { key: "median", label: "Median hours" },
];

export const throughputSeries: ChartSeries[] = [
  { key: "value", label: "PRs merged" },
];

export const deploySeries: ChartSeries[] = [{ key: "value", label: "Deploys" }];

export const teamActivitySeries: ChartSeries[] = [
  { key: "opened", label: "Opened" },
  { key: "merged", label: "Merged" },
];

// --- Daily fixtures for filter-linked charts --------------------------------

const DAY_MS = 24 * 60 * 60 * 1000;

/** Deterministic 0–1 noise so the demo data is stable across renders. */
function pseudoRandom(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/**
 * Generates one year of daily points ending today, with a trend, a weekly
 * seasonal wobble, and deterministic noise. Used to demo how charts respond to
 * the shared range + granularity filters.
 */
function generateDaily({
  base,
  trend,
  amplitude,
  decimals = 0,
  seed = 1,
  days = 365,
}: {
  base: number;
  trend: number;
  amplitude: number;
  decimals?: number;
  seed?: number;
  days?: number;
}): DailyPoint[] {
  const today = startOfDay(new Date()).getTime();
  const points: DailyPoint[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const progress = (days - 1 - i) / days;
    const seasonal = Math.sin(i / 7) * amplitude;
    const noise = (pseudoRandom(seed + i) - 0.5) * amplitude;
    const raw = base * (1 + trend * progress) + seasonal + noise;
    const value = Math.max(0, Number(raw.toFixed(decimals)));
    points.push({ date: toIsoDate(new Date(today - i * DAY_MS)), value });
  }
  return points;
}

/** Daily median cycle time in hours (trending down). Aggregate with `avg`. */
export const mockDailyCycleTime: DailyPoint[] = generateDaily({
  base: 26,
  trend: -0.35,
  amplitude: 5,
  decimals: 1,
  seed: 11,
});

/** Daily PRs merged (trending up). Aggregate with `sum`. */
export const mockDailyThroughput: DailyPoint[] = generateDaily({
  base: 9,
  trend: 0.6,
  amplitude: 4,
  seed: 23,
});

/** Daily production deploys (trending up). Aggregate with `sum`. */
export const mockDailyDeploys: DailyPoint[] = generateDaily({
  base: 4,
  trend: 0.8,
  amplitude: 2,
  seed: 37,
});
