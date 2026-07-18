// Shapes mirror the backend analytics metrics API (app/schemas/metrics.py),
// which serves the dbt-built DORA primitive marts (transformation/dbt). Used by
// the dashboard chart components (home page, My metrics).

import { toIsoDate, type Granularity } from "@/components/charts";
import { authedGet } from "@/lib/api";

/**
 * `org` reads tenant-wide series; `me` restricts PR-based metrics to the
 * signed-in user's authored work (GitHub login resolved server-side).
 */
export type MetricScope = "org" | "me";

export type PullRequestActivityPoint = {
  period_start: string;
  opened: number;
  merged: number;
  closed: number;
};

export type PullRequestActivityResponse = {
  granularity: Granularity;
  points: PullRequestActivityPoint[];
};

export type CycleTimePoint = {
  period_start: string;
  prs_merged: number;
  median_hours: number;
  avg_hours: number;
  p90_hours: number;
};

export type CycleTimeResponse = {
  granularity: Granularity;
  points: CycleTimePoint[];
};

export type ReviewLatencyPoint = {
  period_start: string;
  prs_first_reviewed: number;
  median_hours_to_first_review: number | null;
  reviews_submitted: number;
};

export type ReviewLatencyResponse = {
  granularity: Granularity;
  points: ReviewLatencyPoint[];
};

export type ChangeFailurePoint = {
  period_start: string;
  prs_merged: number;
  prs_reverted: number;
  change_failure_rate: number;
};

export type ChangeFailureResponse = {
  granularity: Granularity;
  points: ChangeFailurePoint[];
};

export type DeploymentFrequencyPoint = {
  period_start: string;
  releases_published: number;
  production_releases: number;
};

export type DeploymentFrequencyResponse = {
  granularity: Granularity;
  points: DeploymentFrequencyPoint[];
};

export type ReviewCommentsPoint = {
  period_start: string;
  review_comments_created: number;
};

export type ReviewCommentsResponse = {
  granularity: Granularity;
  points: ReviewCommentsPoint[];
};

export type WorkflowRunsPoint = {
  period_start: string;
  runs_started: number;
  runs_completed: number;
  runs_success: number;
  runs_failure: number;
};

export type WorkflowRunsResponse = {
  granularity: Granularity;
  points: WorkflowRunsPoint[];
};

export type TicketActivityPoint = {
  period_start: string;
  tickets_created: number;
  tickets_completed: number;
  tickets_canceled: number;
};

export type TicketActivityResponse = {
  granularity: Granularity;
  points: TicketActivityPoint[];
};

export type TicketCommentsPoint = {
  period_start: string;
  comments_created: number;
};

export type TicketCommentsResponse = {
  granularity: Granularity;
  points: TicketCommentsPoint[];
};

export type ProjectActivityPoint = {
  period_start: string;
  projects_created: number;
  projects_completed: number;
  projects_canceled: number;
};

export type ProjectActivityResponse = {
  granularity: Granularity;
  points: ProjectActivityPoint[];
};

export type TicketDescriptionEditsPoint = {
  period_start: string;
  description_edits: number;
};

export type TicketDescriptionEditsResponse = {
  granularity: Granularity;
  points: TicketDescriptionEditsPoint[];
};

type MetricRange = { granularity: Granularity; start: Date; end: Date };
type ScopedMetricRange = MetricRange & { scope?: MetricScope };

function rangeParams(options: ScopedMetricRange): URLSearchParams {
  const params = new URLSearchParams({
    granularity: options.granularity,
    start: toIsoDate(options.start),
    end: toIsoDate(options.end),
  });
  if (options.scope && options.scope !== "org") params.set("scope", options.scope);
  return params;
}

export function getPullRequestActivity(
  token: string,
  tenantId: string,
  options: ScopedMetricRange,
): Promise<PullRequestActivityResponse> {
  const params = rangeParams(options);
  return authedGet<PullRequestActivityResponse>(
    `/api/v1/tenants/${tenantId}/metrics/pull-requests?${params}`,
    token,
  );
}

export function getCycleTime(
  token: string,
  tenantId: string,
  options: ScopedMetricRange,
): Promise<CycleTimeResponse> {
  const params = rangeParams(options);
  return authedGet<CycleTimeResponse>(
    `/api/v1/tenants/${tenantId}/metrics/cycle-time?${params}`,
    token,
  );
}

export function getReviewLatency(
  token: string,
  tenantId: string,
  options: ScopedMetricRange,
): Promise<ReviewLatencyResponse> {
  const params = rangeParams(options);
  return authedGet<ReviewLatencyResponse>(
    `/api/v1/tenants/${tenantId}/metrics/review-latency?${params}`,
    token,
  );
}

export function getChangeFailure(
  token: string,
  tenantId: string,
  options: ScopedMetricRange,
): Promise<ChangeFailureResponse> {
  const params = rangeParams(options);
  return authedGet<ChangeFailureResponse>(
    `/api/v1/tenants/${tenantId}/metrics/change-failure?${params}`,
    token,
  );
}

export function getDeploymentFrequency(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<DeploymentFrequencyResponse> {
  const params = rangeParams(options);
  return authedGet<DeploymentFrequencyResponse>(
    `/api/v1/tenants/${tenantId}/metrics/deployment-frequency?${params}`,
    token,
  );
}

export function getReviewComments(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<ReviewCommentsResponse> {
  const params = rangeParams(options);
  return authedGet<ReviewCommentsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/review-comments?${params}`,
    token,
  );
}

export function getWorkflowRuns(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<WorkflowRunsResponse> {
  const params = rangeParams(options);
  return authedGet<WorkflowRunsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/workflow-runs?${params}`,
    token,
  );
}

export function getTicketActivity(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<TicketActivityResponse> {
  const params = rangeParams(options);
  return authedGet<TicketActivityResponse>(
    `/api/v1/tenants/${tenantId}/metrics/tickets?${params}`,
    token,
  );
}

export function getTicketComments(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<TicketCommentsResponse> {
  const params = rangeParams(options);
  return authedGet<TicketCommentsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/ticket-comments?${params}`,
    token,
  );
}

export function getProjectActivity(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<ProjectActivityResponse> {
  const params = rangeParams(options);
  return authedGet<ProjectActivityResponse>(
    `/api/v1/tenants/${tenantId}/metrics/projects?${params}`,
    token,
  );
}

export function getTicketDescriptionEdits(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<TicketDescriptionEditsResponse> {
  const params = rangeParams(options);
  return authedGet<TicketDescriptionEditsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/ticket-description-edits?${params}`,
    token,
  );
}
