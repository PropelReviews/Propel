import { useEffect, useState } from "react";

import {
  formatCount,
  formatWeekLabel,
  LineChartWidget,
  MetricFiltersBar,
  MetricFiltersProvider,
  useMetricFilters,
  type ChartSeries,
  type TimeSeriesPoint,
} from "@/components/charts";
import { ApiError } from "@/lib/api";
import { getPullRequestActivity } from "@/lib/metrics";
import { useAuth } from "@/providers/auth-provider";

const PR_SERIES: ChartSeries[] = [
  { key: "opened", label: "Opened" },
  { key: "merged", label: "Merged" },
  { key: "closed", label: "Closed" },
];

type FetchState =
  | { status: "loading" }
  | { status: "ready"; data: TimeSeriesPoint[] }
  | { status: "error"; message: string };

/**
 * PR activity over time (opened / merged / closed without merging), served by
 * the dbt mart `analytics.fct_pr_activity_daily` through the metrics API. The
 * shared filter bar drives range + granularity; bucketing happens server-side,
 * so every filter change refetches.
 */
export function PrActivityChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <PrActivityChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function PrActivityChartInner({ tenantId }: { tenantId: string }) {
  const { token } = useAuth();
  const { filters, dateRange } = useMetricFilters();
  const [state, setState] = useState<FetchState>({ status: "loading" });

  const { granularity } = filters;
  const startMs = dateRange.start.getTime();
  const endMs = dateRange.end.getTime();

  useEffect(() => {
    if (!token) return;

    let cancelled = false;
    (async () => {
      setState({ status: "loading" });
      try {
        const response = await getPullRequestActivity(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            opened: point.opened,
            merged: point.merged,
            closed: point.closed,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError
            ? error.message
            : "Could not load pull request activity.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Pull request activity"
      description="PRs opened, merged, and closed without merging"
      data={state.status === "ready" ? state.data : []}
      series={PR_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No pull request activity in this range yet."
      }
    />
  );
}
