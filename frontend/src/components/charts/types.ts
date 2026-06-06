import type { ReactNode } from "react";

/**
 * A single row of chart data. Keys map to series keys (numeric values) plus one
 * axis key (the category or time label, a string).
 */
export type ChartDataPoint = Record<string, string | number>;

/** Convenience alias for time-based data keyed by an ISO date string. */
export type TimeSeriesPoint = { date: string } & Record<string, string | number>;

/** Convenience alias for categorical data keyed by a category label. */
export type CategoryPoint = { category: string } & Record<string, string | number>;

/** Maps a data key to its display label and optional color. */
export interface ChartSeries {
  /** Key in each data point that holds this series' numeric value. */
  key: string;
  /** Human-readable label shown in the legend and tooltip. */
  label: string;
  /**
   * CSS color for the series. Defaults to a rotating `--chart-N` design token
   * when omitted, so colors always come from the theme.
   */
  color?: string;
}

/** Formats a numeric series value for axes and tooltips. */
export type ValueFormatter = (value: number) => string;

/** Formats an axis category/date label. */
export type AxisFormatter = (value: string) => string;

/** Props shared by every chart primitive (the card-less, drop-anywhere charts). */
export interface ChartPrimitiveProps {
  data: ChartDataPoint[];
  series: ChartSeries[];
  /** Key used for the category/time axis. Defaults to `"date"`. */
  xKey?: string;
  /** Chart height in pixels. Defaults to {@link DEFAULT_CHART_HEIGHT}. */
  height?: number;
  className?: string;
  /** Formats series values shown on the y-axis and in tooltips. */
  valueFormatter?: ValueFormatter;
  /** Formats the x-axis tick labels. */
  xFormatter?: AxisFormatter;
  /** Message shown when `data` is empty. */
  emptyMessage?: string;
  /** Renders a skeleton placeholder instead of the chart. */
  isLoading?: boolean;
}

/** Props shared by every chart widget (a primitive wrapped in a titled card). */
export interface ChartWidgetProps {
  title: ReactNode;
  description?: ReactNode;
  /** Footer text or node, e.g. a time-range caption. */
  footer?: ReactNode;
  className?: string;
}
