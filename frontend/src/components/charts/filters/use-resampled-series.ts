import { useMemo } from "react";

import type { TimeSeriesPoint } from "../types";
import { useMetricFilters } from "./metric-filters-context";
import { resample, type Aggregation, type DailyPoint } from "./time";

/**
 * Connects a daily metric series to the shared filters: resamples `points` to
 * the active range + granularity and returns chart-ready {@link TimeSeriesPoint}s.
 * This is what makes a chart "linked" — it re-derives its data whenever the
 * shared date picker changes.
 */
export function useResampledSeries(
  points: DailyPoint[],
  {
    how = "sum",
    valueKey = "value",
  }: { how?: Aggregation; valueKey?: string } = {},
): TimeSeriesPoint[] {
  const { filters } = useMetricFilters();

  return useMemo(
    () =>
      resample(points, {
        range: filters.range,
        granularity: filters.granularity,
        how,
      }).map((point) => ({ date: point.date, [valueKey]: point.value })),
    [points, filters.range, filters.granularity, how, valueKey],
  );
}
