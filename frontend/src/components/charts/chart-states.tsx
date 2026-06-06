import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

import { DEFAULT_CHART_HEIGHT } from "./config";

interface ChartStateProps {
  height?: number;
  className?: string;
}

/** Centered muted message shown when a chart has no data. */
export function ChartEmptyState({
  height = DEFAULT_CHART_HEIGHT,
  className,
  message = "No data available",
}: ChartStateProps & { message?: string }) {
  return (
    <div
      data-slot="chart-empty"
      role="status"
      className={cn(
        "text-muted-foreground flex items-center justify-center text-sm",
        className,
      )}
      style={{ height }}
    >
      {message}
    </div>
  );
}

/** Skeleton placeholder matching a chart's footprint while data loads. */
export function ChartLoadingState({
  height = DEFAULT_CHART_HEIGHT,
  className,
}: ChartStateProps) {
  return (
    <Skeleton
      data-slot="chart-loading"
      className={cn("w-full", className)}
      style={{ height }}
    />
  );
}
