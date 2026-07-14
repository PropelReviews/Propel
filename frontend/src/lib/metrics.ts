// Shapes mirror the backend analytics metrics API (app/schemas/metrics.py),
// which serves the dbt-built DORA primitive marts (transformation/dbt). Used by
// the /data page.

import { toIsoDate, type Granularity } from "@/components/charts";
import { authedGet } from "@/lib/api";

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

export type LinearIssueActivityPoint = {
  period_start: string;
  issues_created: number;
  issues_completed: number;
  issues_canceled: number;
};

export type LinearIssueActivityResponse = {
  granularity: Granularity;
  points: LinearIssueActivityPoint[];
};

export type LinearCommentsPoint = {
  period_start: string;
  comments_created: number;
};

export type LinearCommentsResponse = {
  granularity: Granularity;
  points: LinearCommentsPoint[];
};

export type LinearProjectsPoint = {
  period_start: string;
  projects_created: number;
  projects_completed: number;
  projects_canceled: number;
};

export type LinearProjectsResponse = {
  granularity: Granularity;
  points: LinearProjectsPoint[];
};

export type LinearDescriptionEditsPoint = {
  period_start: string;
  description_edits: number;
};

export type LinearDescriptionEditsResponse = {
  granularity: Granularity;
  points: LinearDescriptionEditsPoint[];
};

type MetricRange = { granularity: Granularity; start: Date; end: Date };

function rangeParams(options: MetricRange): URLSearchParams {
  return new URLSearchParams({
    granularity: options.granularity,
    start: toIsoDate(options.start),
    end: toIsoDate(options.end),
  });
}

export function getPullRequestActivity(
  token: string,
  tenantId: string,
  options: MetricRange,
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
  options: MetricRange,
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
  options: MetricRange,
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
  options: MetricRange,
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

export function getLinearIssueActivity(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<LinearIssueActivityResponse> {
  const params = rangeParams(options);
  return authedGet<LinearIssueActivityResponse>(
    `/api/v1/tenants/${tenantId}/metrics/linear/issues?${params}`,
    token,
  );
}

export function getLinearComments(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<LinearCommentsResponse> {
  const params = rangeParams(options);
  return authedGet<LinearCommentsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/linear/comments?${params}`,
    token,
  );
}

export function getLinearProjects(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<LinearProjectsResponse> {
  const params = rangeParams(options);
  return authedGet<LinearProjectsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/linear/projects?${params}`,
    token,
  );
}

export function getLinearDescriptionEdits(
  token: string,
  tenantId: string,
  options: MetricRange,
): Promise<LinearDescriptionEditsResponse> {
  const params = rangeParams(options);
  return authedGet<LinearDescriptionEditsResponse>(
    `/api/v1/tenants/${tenantId}/metrics/linear/description-edits?${params}`,
    token,
  );
}
