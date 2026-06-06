// Shapes mirror the backend ingestion observability API
// (app/schemas/ingestion.py). Used by the /data page.

import { authedGet } from "@/lib/api";

export type IngestionRunStatus = "running" | "success" | "error";

export type IngestionRun = {
  id: string;
  connected_account_id: string;
  source: string;
  resource_type: string | null;
  status: IngestionRunStatus;
  started_at: string;
  finished_at: string | null;
  records_pulled: number;
  datapoints_written: number;
  error: string | null;
};

export type CountByLabel = {
  label: string;
  count: number;
};

export type IngestionStats = {
  total_datapoints: number;
  total_raw_records: number;
  by_kind: CountByLabel[];
  by_source: CountByLabel[];
  last_run_at: string | null;
};

export function listIngestionRuns(
  token: string,
  tenantId: string,
  limit = 20,
): Promise<IngestionRun[]> {
  return authedGet<IngestionRun[]>(
    `/api/v1/tenants/${tenantId}/ingestion/runs?limit=${limit}`,
    token,
  );
}

export function getIngestionStats(
  token: string,
  tenantId: string,
): Promise<IngestionStats> {
  return authedGet<IngestionStats>(
    `/api/v1/tenants/${tenantId}/ingestion/stats`,
    token,
  );
}
