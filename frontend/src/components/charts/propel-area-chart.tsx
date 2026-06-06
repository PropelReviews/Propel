import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { cn } from "@/lib/utils";

import { ChartEmptyState, ChartLoadingState } from "./chart-states";
import { buildChartConfig, DEFAULT_CHART_HEIGHT, DEFAULT_CHART_MARGIN } from "./config";
import type { ChartPrimitiveProps } from "./types";

/**
 * Card-less area chart for cumulative or volume-over-time metrics. Each series
 * renders a softly filled `<Area>`; multiple series stack.
 */
export function PropelAreaChart({
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
      <ChartEmptyState height={height} className={className} message={emptyMessage} />
    );
  }

  const config = buildChartConfig(series);
  const stacked = series.length > 1;

  return (
    <ChartContainer
      config={config}
      className={cn("aspect-auto w-full", className)}
      style={{ height }}
    >
      <AreaChart accessibilityLayer data={data} margin={DEFAULT_CHART_MARGIN}>
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
        {stacked ? <ChartLegend content={<ChartLegendContent />} /> : null}
        {series.map((item) => (
          <Area
            key={item.key}
            dataKey={item.key}
            type="monotone"
            stackId={stacked ? "stack" : undefined}
            stroke={`var(--color-${item.key})`}
            fill={`var(--color-${item.key})`}
            fillOpacity={0.2}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ChartContainer>
  );
}
