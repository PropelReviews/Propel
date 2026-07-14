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
import {
  getProjectActivity,
  getReviewComments,
  getTicketActivity,
  getTicketComments,
  getTicketDescriptionEdits,
  getWorkflowRuns,
} from "@/lib/metrics";
import { useAuth } from "@/providers/auth-provider";

type FetchState =
  | { status: "loading" }
  | { status: "ready"; data: TimeSeriesPoint[] }
  | { status: "error"; message: string };

const REVIEW_COMMENT_SERIES: ChartSeries[] = [
  { key: "review_comments_created", label: "Review comments" },
];

const WORKFLOW_RUN_SERIES: ChartSeries[] = [
  { key: "runs_started", label: "Started" },
  { key: "runs_success", label: "Success" },
  { key: "runs_failure", label: "Failure" },
];

const TICKET_SERIES: ChartSeries[] = [
  { key: "tickets_created", label: "Created" },
  { key: "tickets_completed", label: "Completed" },
  { key: "tickets_canceled", label: "Canceled" },
];

const TICKET_COMMENT_SERIES: ChartSeries[] = [
  { key: "comments_created", label: "Comments" },
];

const PROJECT_SERIES: ChartSeries[] = [
  { key: "projects_created", label: "Created" },
  { key: "projects_completed", label: "Completed" },
];

const DESCRIPTION_EDIT_SERIES: ChartSeries[] = [
  { key: "description_edits", label: "Description edits" },
];

/** GitHub PR review-comment throughput. */
export function ReviewCommentsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <ReviewCommentsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function ReviewCommentsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getReviewComments(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            review_comments_created: point.review_comments_created,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError
              ? error.message
              : "Could not load review comments.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Review comments"
      description="Line-level comments on pull-request reviews"
      data={state.status === "ready" ? state.data : []}
      series={REVIEW_COMMENT_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No review comments in this range yet."
      }
    />
  );
}

/** GitHub Actions workflow-run activity. */
export function WorkflowRunsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <WorkflowRunsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function WorkflowRunsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getWorkflowRuns(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            runs_started: point.runs_started,
            runs_success: point.runs_success,
            runs_failure: point.runs_failure,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError ? error.message : "Could not load workflow runs.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Action runs"
      description="GitHub Actions workflow runs started, succeeded, and failed"
      data={state.status === "ready" ? state.data : []}
      series={WORKFLOW_RUN_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No Actions workflow runs in this range yet."
      }
    />
  );
}

/** Ticket activity across issue trackers (GitHub, Linear, …). */
export function TicketActivityChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <TicketActivityChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function TicketActivityChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getTicketActivity(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            tickets_created: point.tickets_created,
            tickets_completed: point.tickets_completed,
            tickets_canceled: point.tickets_canceled,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError ? error.message : "Could not load tickets.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Tickets"
      description="Tickets created, completed, and canceled across connected trackers"
      data={state.status === "ready" ? state.data : []}
      series={TICKET_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No ticket activity in this range yet."
      }
    />
  );
}

/** Ticket comment throughput across issue trackers. */
export function TicketCommentsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <TicketCommentsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function TicketCommentsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getTicketComments(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            comments_created: point.comments_created,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError
              ? error.message
              : "Could not load ticket comments.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Ticket comments"
      description="Comments on tickets across connected trackers"
      data={state.status === "ready" ? state.data : []}
      series={TICKET_COMMENT_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No ticket comments in this range yet."
      }
    />
  );
}

/** Project activity across project trackers. */
export function ProjectActivityChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <ProjectActivityChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function ProjectActivityChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getProjectActivity(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            projects_created: point.projects_created,
            projects_completed: point.projects_completed,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError ? error.message : "Could not load projects.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Projects"
      description="Projects created and completed across connected trackers"
      data={state.status === "ready" ? state.data : []}
      series={PROJECT_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error" ? state.message : "No projects in this range yet."
      }
    />
  );
}

/** Ticket description edits across issue trackers. */
export function TicketDescriptionEditsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <TicketDescriptionEditsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function TicketDescriptionEditsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getTicketDescriptionEdits(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            description_edits: point.description_edits,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError
              ? error.message
              : "Could not load description edits.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Description edits"
      description="Times ticket descriptions were edited across connected trackers"
      data={state.status === "ready" ? state.data : []}
      series={DESCRIPTION_EDIT_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No description edits in this range yet."
      }
    />
  );
}
