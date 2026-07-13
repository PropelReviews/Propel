import { useEffect, useState } from "react";

import {
  formatDuration,
  formatPercent,
  formatWeekLabel,
  LineChartWidget,
  MetricFiltersBar,
  MetricFiltersProvider,
  useMetricFilters,
  type ChartSeries,
  type TimeSeriesPoint,
} from "@/components/charts";
import { ApiError } from "@/lib/api";
import { getChangeFailure, getCycleTime, getReviewLatency } from "@/lib/metrics";
import { useAuth } from "@/providers/auth-provider";

type FetchState =
  | { status: "loading" }
  | { status: "ready"; data: TimeSeriesPoint[] }
  | { status: "error"; message: string };

const CYCLE_SERIES: ChartSeries[] = [
  { key: "median_hours", label: "Median" },
  { key: "p90_hours", label: "p90" },
];

const REVIEW_SERIES: ChartSeries[] = [
  { key: "median_hours_to_first_review", label: "Median hours to first review" },
];

const CFR_SERIES: ChartSeries[] = [
  { key: "change_failure_rate_pct", label: "Change failure rate" },
];

/**
 * DORA lead-time proxy: median / p90 hours from PR open to merge
 * (`analytics.fct_pr_cycle_time_daily`).
 */
export function CycleTimeChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <CycleTimeChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function CycleTimeChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getCycleTime(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            median_hours: point.median_hours,
            p90_hours: point.p90_hours,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Could not load cycle time.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Cycle time"
      description="Hours from PR open to merge (DORA lead-time proxy)"
      data={state.status === "ready" ? state.data : []}
      series={CYCLE_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatDuration}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No cycle time data in this range yet."
      }
    />
  );
}

/**
 * Time to first non-author review (`analytics.fct_review_latency_daily`).
 */
export function ReviewLatencyChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <ReviewLatencyChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function ReviewLatencyChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getReviewLatency(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.flatMap((point) =>
            point.median_hours_to_first_review == null
              ? []
              : [
                  {
                    date: point.period_start,
                    median_hours_to_first_review: point.median_hours_to_first_review,
                  },
                ],
          ),
        });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Could not load review latency.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Time to first review"
      description="Hours from PR open to first non-author review"
      data={state.status === "ready" ? state.data : []}
      series={REVIEW_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatDuration}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No review latency data in this range yet."
      }
    />
  );
}

/**
 * Change-failure proxy via revert-titled merges
 * (`analytics.fct_change_failure_daily`).
 */
export function ChangeFailureChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <ChangeFailureChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function ChangeFailureChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getChangeFailure(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            change_failure_rate_pct: point.change_failure_rate * 100,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError
            ? error.message
            : "Could not load change failure rate.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Change failure rate"
      description="Share of merges whose title looks like a revert (DORA CFR proxy)"
      data={state.status === "ready" ? state.data : []}
      series={CFR_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatPercent}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No change-failure data in this range yet."
      }
    />
  );
}
