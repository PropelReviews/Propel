// Public surface for the Propel chart design library. Import widgets and
// primitives from here so call sites never reach into individual files.

export type {
  AxisFormatter,
  CategoryPoint,
  ChartDataPoint,
  ChartPrimitiveProps,
  ChartSeries,
  ChartWidgetProps,
  TimeSeriesPoint,
  ValueFormatter,
} from "./types";

export {
  buildChartConfig,
  CHART_COLORS,
  DEFAULT_CHART_HEIGHT,
  DEFAULT_CHART_MARGIN,
  resolveSeriesColor,
} from "./config";

export {
  formatCount,
  formatDuration,
  formatPercent,
  formatWeekLabel,
} from "./formatters";

export { ChartEmptyState, ChartLoadingState } from "./chart-states";

// Primitives (card-less, drop anywhere)
export { PropelLineChart } from "./propel-line-chart";
export { PropelBarChart } from "./propel-bar-chart";
export { PropelAreaChart } from "./propel-area-chart";
export { MetricSparkline } from "./metric-sparkline";

// Widgets (card-wrapped, titled)
export { ChartWidget } from "./chart-widget";
export { LineChartWidget, type LineChartWidgetProps } from "./line-chart-widget";
export { BarChartWidget, type BarChartWidgetProps } from "./bar-chart-widget";
export { AreaChartWidget, type AreaChartWidgetProps } from "./area-chart-widget";
export { MetricCard, type MetricCardProps } from "./metric-card";

// Shared date-range + granularity filters (the linking layer)
export * from "./filters";
