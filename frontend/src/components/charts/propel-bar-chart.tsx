import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

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
 * Card-less bar chart for categorical comparisons (e.g. PRs merged by team).
 * Each series renders a grouped `<Bar>`.
 */
export function PropelBarChart({
  data,
  series,
  xKey = "category",
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
      <BarChart accessibilityLayer data={data} margin={DEFAULT_CHART_MARGIN}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey={xKey}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          tickFormatter={xFormatter}
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
          <Bar
            key={item.key}
            dataKey={item.key}
            fill={`var(--color-${item.key})`}
            radius={[4, 4, 0, 0]}
          />
        ))}
      </BarChart>
    </ChartContainer>
  );
}
