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
