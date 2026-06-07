import { Line, LineChart } from "recharts";

import { ChartContainer } from "@/components/ui/chart";
import { cn } from "@/lib/utils";

import { CHART_COLORS } from "./config";
import type { ChartDataPoint } from "./types";

interface MetricSparklineProps {
  data: ChartDataPoint[];
  /** Key holding the numeric value to plot. Defaults to `"value"`. */
  dataKey?: string;
  /** Line color. Defaults to the first `--chart-N` token. */
  color?: string;
  height?: number;
  className?: string;
}

/**
 * Tiny, axis-less trend line for inline use in tables or KPI rows. No grid,
 * tooltip, or legend — just the shape of the trend.
 */
export function MetricSparkline({
  data,
  dataKey = "value",
  color = CHART_COLORS[1],
  height = 40,
  className,
}: MetricSparklineProps) {
  if (data.length === 0) return null;

  return (
    <ChartContainer
      config={{ [dataKey]: { color } }}
      className={cn("aspect-auto w-full", className)}
      style={{ height }}
    >
      <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <Line
          dataKey={dataKey}
          type="monotone"
          stroke={`var(--color-${dataKey})`}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  );
}
