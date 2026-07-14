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
  getLinearComments,
  getLinearDescriptionEdits,
  getLinearIssueActivity,
  getLinearProjects,
  getReviewComments,
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

const LINEAR_ISSUE_SERIES: ChartSeries[] = [
  { key: "issues_created", label: "Created" },
  { key: "issues_completed", label: "Completed" },
  { key: "issues_canceled", label: "Canceled" },
];

const LINEAR_COMMENT_SERIES: ChartSeries[] = [
  { key: "comments_created", label: "Comments" },
];

const LINEAR_PROJECT_SERIES: ChartSeries[] = [
  { key: "projects_created", label: "Created" },
  { key: "projects_completed", label: "Completed" },
];

const LINEAR_DESCRIPTION_EDIT_SERIES: ChartSeries[] = [
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

/** Linear issue created / completed / canceled. */
export function LinearIssueActivityChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <LinearIssueActivityChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function LinearIssueActivityChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getLinearIssueActivity(token, tenantId, {
          granularity,
          start: new Date(startMs),
          end: new Date(endMs),
        });
        if (cancelled) return;
        setState({
          status: "ready",
          data: response.points.map((point) => ({
            date: point.period_start,
            issues_created: point.issues_created,
            issues_completed: point.issues_completed,
            issues_canceled: point.issues_canceled,
          })),
        });
      } catch (error) {
        if (cancelled) return;
        setState({
          status: "error",
          message:
            error instanceof ApiError ? error.message : "Could not load Linear issues.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Linear issues"
      description="Issues created, completed, and canceled"
      data={state.status === "ready" ? state.data : []}
      series={LINEAR_ISSUE_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error" ? state.message : "No Linear issues in this range yet."
      }
    />
  );
}

/** Linear comment throughput. */
export function LinearCommentsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <LinearCommentsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function LinearCommentsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getLinearComments(token, tenantId, {
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
              : "Could not load Linear comments.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Linear comments"
      description="Comments created on issues and projects"
      data={state.status === "ready" ? state.data : []}
      series={LINEAR_COMMENT_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No Linear comments in this range yet."
      }
    />
  );
}

/** Linear project activity. */
export function LinearProjectsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <LinearProjectsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function LinearProjectsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getLinearProjects(token, tenantId, {
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
            error instanceof ApiError
              ? error.message
              : "Could not load Linear projects.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, granularity, startMs, endMs]);

  return (
    <LineChartWidget
      title="Linear projects"
      description="Projects created and completed"
      data={state.status === "ready" ? state.data : []}
      series={LINEAR_PROJECT_SERIES}
      xFormatter={formatWeekLabel}
      valueFormatter={formatCount}
      isLoading={state.status === "loading"}
      emptyMessage={
        state.status === "error"
          ? state.message
          : "No Linear projects in this range yet."
      }
    />
  );
}

/** Linear issue description edits. */
export function LinearDescriptionEditsChart({ tenantId }: { tenantId: string }) {
  return (
    <MetricFiltersProvider initialRange="quarter">
      <div className="mb-4">
        <MetricFiltersBar />
      </div>
      <LinearDescriptionEditsChartInner tenantId={tenantId} />
    </MetricFiltersProvider>
  );
}

function LinearDescriptionEditsChartInner({ tenantId }: { tenantId: string }) {
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
        const response = await getLinearDescriptionEdits(token, tenantId, {
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
      description="Times Linear issue descriptions were edited"
      data={state.status === "ready" ? state.data : []}
      series={LINEAR_DESCRIPTION_EDIT_SERIES}
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
