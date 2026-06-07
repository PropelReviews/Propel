// Shapes that mirror the future backend metrics API. The mock data conforms to
// these, so swapping to the real API later is a matter of replacing the data
// source — chart components and the `toChartData` adapter stay the same.

export type MetricUnit = "hours" | "count" | "percent";

/** A single period's value within a metric time series. */
export interface MetricPoint {
  /** ISO date marking the start of the period (e.g. a week). */
  period: string;
  value: number;
}

/** A single metric tracked over time. */
export interface MetricTimeSeriesResponse {
  metric: string;
  unit: MetricUnit;
  points: MetricPoint[];
}

/** One row of a categorical breakdown (e.g. PRs merged per team). */
export interface MetricBreakdownRow {
  category: string;
  values: Record<string, number>;
}

/** A categorical metric broken down by some dimension. */
export interface MetricBreakdownResponse {
  metric: string;
  unit: MetricUnit;
  /** Series keys present in every row's `values`. */
  seriesKeys: string[];
  rows: MetricBreakdownRow[];
}

/** A headline KPI with an optional period-over-period delta. */
export interface MetricSummary {
  metric: string;
  unit: MetricUnit;
  value: number;
  /** Signed percentage change versus the previous period. */
  deltaPercent: number;
  /** Whether an increase is a good outcome for this metric. */
  higherIsBetter: boolean;
}
