import type { ChartConfig } from "@/components/ui/chart";

import type { ChartSeries } from "./types";

/**
 * Series colors, drawn from the theme's `--chart-N` tokens (see `index.css`).
 * Series without an explicit color cycle through these in order.
 */
export const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
] as const;

/** Default chart height in pixels. */
export const DEFAULT_CHART_HEIGHT = 240;

/** Default Recharts plot margin, leaving room for axis labels. */
export const DEFAULT_CHART_MARGIN = { top: 8, right: 12, bottom: 0, left: 0 };

/** Resolves a series' color, falling back to a rotating theme token. */
export function resolveSeriesColor(series: ChartSeries, index: number): string {
  return series.color ?? CHART_COLORS[index % CHART_COLORS.length];
}

/**
 * Builds the shadcn {@link ChartConfig} from a list of series. This wires each
 * series key to its label and a `--color-{key}` CSS variable that the chart
 * primitives reference, so call sites never touch raw colors.
 */
export function buildChartConfig(series: ChartSeries[]): ChartConfig {
  return series.reduce<ChartConfig>((config, item, index) => {
    config[item.key] = {
      label: item.label,
      color: resolveSeriesColor(item, index),
    };
    return config;
  }, {});
}
