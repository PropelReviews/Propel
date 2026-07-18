import { useEffect, useState } from "react";

import {
  formatCount,
  formatDuration,
  formatPercent,
  formatWeekLabel,
  PropelLineChart,
  useMetricFilters,
  type ChartSeries,
  type TimeSeriesPoint,
  type ValueFormatter,
} from "@/components/charts";
import type { MetricCatalogItem } from "@/features/metrics/api/metric-definitions";
import { ApiError } from "@/lib/api";
import { getMetricValues } from "@/lib/metrics";
import { useAuth } from "@/providers/auth-provider";

type FetchState =
  | { status: "loading" }
  | { status: "ready"; data: TimeSeriesPoint[] }
  | { status: "error"; message: string };

function valueFormatterFor(metric: MetricCatalogItem): ValueFormatter {
  const unit = metric.display?.unit;
  if (unit === "duration") {
    // Declarative duration metrics store seconds; charts show hours.
    return (seconds) => formatDuration(seconds / 3600);
  }
  if (unit === "percent") {
    return (value) => formatPercent(value <= 1 ? value * 100 : value);
  }
  return formatCount;
}

/**
 * Generic dashboard tile chart: one enrolled metric from
 * ``GET .../metrics/values``, driven by the ambient dashboard filters.
 */
export function MetricValueChart({
  tenantId,
  metric,
  height,
}: {
  tenantId: string;
  metric: MetricCatalogItem;
  height?: number;
}) {
  const { token } = useAuth();
  const { filters, dateRange } = useMetricFilters();
  const [state, setState] = useState<FetchState>({ status: "loading" });

  const { granularity } = filters;
  const startMs = dateRange.start.getTime();
  const endMs = dateRange.end.getTime();
  const metricId = metric.metric_id;

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      setState({ status: "loading" });
      try {
        const response = await getMetricValues(token, tenantId, metricId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.flatMap((point) => {
            if (point.value == null) return [];
            return [{ date: point.period_start, value: point.value }];
          }),
        });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : `Could not load ${metric.name}.`;
        setState({ status: "error", message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, metricId, metric.name, granularity, startMs, endMs]);

  const series: ChartSeries[] = [{ key: "value", label: metric.name }];

  return (
    <PropelLineChart
      data={state.status === "ready" ? state.data : []}
      series={series}
      xFormatter={formatWeekLabel}
      valueFormatter={valueFormatterFor(metric)}
      height={height}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No data for this metric in the selected range."
      }
    />
  );
}
