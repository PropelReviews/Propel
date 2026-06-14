// Shapes mirror the backend analytics metrics API (app/schemas/metrics.py),
// which serves the dbt-built marts (transformation/dbt). Used by the /data page.

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

export function getPullRequestActivity(
  tenantId: string,
  options: { granularity: Granularity; start: Date; end: Date },
): Promise<PullRequestActivityResponse> {
  const params = new URLSearchParams({
    granularity: options.granularity,
    start: toIsoDate(options.start),
    end: toIsoDate(options.end),
  });
  return authedGet<PullRequestActivityResponse>(
    `/api/v1/tenants/${tenantId}/metrics/pull-requests?${params}`,
  );
}
