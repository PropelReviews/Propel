import type { ReactNode } from "react";
import { TrendingDown, TrendingUp } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { MetricSparkline } from "./metric-sparkline";
import type { ChartDataPoint } from "./types";

export interface MetricCardProps {
  /** Metric name shown as the card title. */
  label: ReactNode;
  /** Formatted value shown prominently (e.g. `"18.4h"`). */
  value: ReactNode;
  /** Optional supporting caption under the title. */
  description?: ReactNode;
  /**
   * Period-over-period change as a signed percentage. Positive renders an
   * "up" badge, negative a "down" badge.
   */
  delta?: number;
  /**
   * Whether an increase is good. Cycle time going up is bad; throughput going
   * up is good. Controls the delta badge color. Defaults to `true`.
   */
  higherIsBetter?: boolean;
  /** Optional trend data for an inline sparkline. */
  sparklineData?: ChartDataPoint[];
  /** Key in `sparklineData` holding the numeric value. Defaults to `"value"`. */
  sparklineKey?: string;
  className?: string;
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)}%`;
}

/**
 * KPI tile: a large value with an optional period-over-period delta badge and
 * an optional inline sparkline. Denser than {@link ChartWidget}, for headline
 * numbers.
 */
export function MetricCard({
  label,
  value,
  description,
  delta,
  higherIsBetter = true,
  sparklineData,
  sparklineKey = "value",
  className,
}: MetricCardProps) {
  const hasDelta = delta !== undefined && delta !== 0;
  const isPositive = (delta ?? 0) > 0;
  const isGood = isPositive === higherIsBetter;
  const DeltaIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <Card data-slot="metric-card" size="sm" className={cn("gap-0", className)}>
      <CardHeader>
        <CardTitle className="text-muted-foreground text-sm font-medium">
          {label}
        </CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="flex items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-2xl font-semibold tracking-tight tabular-nums">
            {value}
          </span>
          {hasDelta ? (
            <Badge
              variant={isGood ? "secondary" : "destructive"}
              className="gap-1"
            >
              <DeltaIcon />
              {formatDelta(delta!)}
            </Badge>
          ) : null}
        </div>
        {sparklineData && sparklineData.length > 0 ? (
          <MetricSparkline
            data={sparklineData}
            dataKey={sparklineKey}
            className="max-w-[120px] flex-1"
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
