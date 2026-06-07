import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { cn } from "@/lib/utils";

import { ChartEmptyState, ChartLoadingState } from "./chart-states";
import {
  buildChartConfig,
  DEFAULT_CHART_HEIGHT,
  DEFAULT_CHART_MARGIN,
} from "./config";
import type { ChartPrimitiveProps } from "./types";

/**
 * Card-less line chart. Drop it into any layout; pass typed `data` + `series`
 * and the component handles colors, axes, tooltip, legend, and empty/loading
 * states. One `<Line>` is rendered per series.
 */
export function PropelLineChart({
  data,
  series,
  xKey = "date",
  height = DEFAULT_CHART_HEIGHT,
  className,
  valueFormatter,
  xFormatter,
  emptyMessage,
  isLoading = false,
}: ChartPrimitiveProps) {
  if (isLoading) {
    return <ChartLoadingState height={height} className={className} />;
  }

  if (data.length === 0) {
    return (
      <ChartEmptyState
        height={height}
        className={className}
        message={emptyMessage}
      />
    );
  }

  const config = buildChartConfig(series);

  return (
    <ChartContainer
      config={config}
      className={cn("aspect-auto w-full", className)}
      style={{ height }}
    >
      <LineChart accessibilityLayer data={data} margin={DEFAULT_CHART_MARGIN}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey={xKey}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={xFormatter}
          minTickGap={16}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          width={40}
          tickFormatter={valueFormatter}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        {series.length > 1 ? (
          <ChartLegend content={<ChartLegendContent />} />
        ) : null}
        {series.map((item) => (
          <Line
            key={item.key}
            dataKey={item.key}
            type="monotone"
            stroke={`var(--color-${item.key})`}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ChartContainer>
  );
}
