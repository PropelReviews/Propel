/**
 * Typed client for metric definition / catalog APIs (M4 + M5).
 * Paths use tenant UUID; store org_id on the server is the tenant slug.
 */

import { authedGet, authedRequest } from "@/lib/api";

export type MetricSource = "standard" | "standard_customized" | "custom" | "variant";

export type MetricCatalogItem = {
  metric_id: string;
  name: string;
  version: number;
  revision: number;
  status: string;
  content_hash: string | null;
  visibility: string | null;
  description: string | null;
  tags: string[];
  entity: string | null;
  source: MetricSource;
  extends: string | null;
  params_bound: Record<string, unknown> | null;
  draft_pending: boolean;
  notices: Array<{ id?: string; notice: string; payload?: Record<string, unknown> }>;
  compile_error: string | null;
  updated_at: string | null;
  enrolled: boolean;
};

export type MetricDefinitionDetail = {
  org_id: string;
  metric_id: string;
  version: number;
  revision: number;
  status: string;
  kind: string;
  yaml: string;
  resolved_json: Record<string, unknown> | null;
  content_hash: string | null;
  parent_pin: Record<string, unknown> | null;
  notices: Array<{ id?: string; notice: string; payload?: Record<string, unknown> }>;
  created_by: string | null;
  created_at: string | null;
};

export type MetricVersion = {
  metric_id: string;
  version: number;
  revision: number;
  status: string;
  content_hash: string | null;
  created_by: string | null;
  created_at: string | null;
  org_id: string;
};

export type MetricCatalogField = {
  name: string;
  type: string;
  role: string;
  values: string[] | null;
  nullable: boolean | null;
  cardinality_estimate: number | null;
  person: boolean;
  virtual: boolean;
  mapping_id: string | null;
};

export type MetricCatalogEntity = {
  name: string;
  grain: string | null;
  dbt_model: string | null;
  fields: MetricCatalogField[];
};

export type MetricCatalogResponse = {
  catalog_version: number;
  cardinality: Record<string, number>;
  entities: MetricCatalogEntity[];
  virtual_dimensions: Array<{
    mapping_id: string;
    entity: string;
    from_field: string;
    to_dimension: string;
  }>;
};

export type DiffResponse = {
  changes: Array<{
    path: string;
    op: string;
    before?: unknown;
    after?: unknown;
  }>;
  summary: string[];
  from_resolved: Record<string, unknown> | null;
  to_resolved: Record<string, unknown> | null;
};

export type MetricSetRead = {
  org: string;
  yaml: string | null;
  doc: Record<string, unknown>;
  version: number | null;
  status: string;
};

export type DimensionMappingSummary = {
  mapping_id: string;
  entity: string | null;
  from_field: string | null;
  to_dimension: string | null;
  version: number;
  status: string;
};

export type CompileRun = {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  trigger: string;
  report_json: Record<string, unknown> | null;
};

export type MetricHealthSummary = {
  broken_count: number;
  notice_count: number;
  open_parent_version_notices: number;
  recent_compile_runs: CompileRun[];
  broken_metrics: Array<{
    metric_id: string;
    version: number;
    content_hash: string | null;
  }>;
};

export type GeneratedSql = {
  metric_id: string;
  content_hash: string | null;
  sql: string;
  source: "file" | "db" | "missing";
};

function base(tenantId: string) {
  return `/api/v1/tenants/${tenantId}`;
}

export function listMetricDefinitions(
  token: string,
  tenantId: string,
  options: {
    referencable?: boolean;
    entity?: string;
    includeDrafts?: boolean;
    includeBroken?: boolean;
  } = {},
): Promise<MetricCatalogItem[]> {
  const params = new URLSearchParams();
  if (options.referencable) params.set("referencable", "true");
  if (options.entity) params.set("entity", options.entity);
  if (options.includeDrafts === false) params.set("include_drafts", "false");
  if (options.includeBroken === false) params.set("include_broken", "false");
  const qs = params.toString();
  return authedGet(`${base(tenantId)}/metric-definitions${qs ? `?${qs}` : ""}`, token);
}

export function getMetricCatalog(
  token: string,
  tenantId: string,
): Promise<MetricCatalogResponse> {
  return authedGet(`${base(tenantId)}/metric-catalog`, token);
}

export function getMetricDefinition(
  token: string,
  tenantId: string,
  metricId: string,
): Promise<MetricDefinitionDetail> {
  const params = new URLSearchParams({ metric_id: metricId });
  return authedGet(`${base(tenantId)}/metric-definitions/detail?${params}`, token);
}

export function listMetricVersions(
  token: string,
  tenantId: string,
  metricId: string,
): Promise<MetricVersion[]> {
  const params = new URLSearchParams({ metric_id: metricId });
  return authedGet(`${base(tenantId)}/metric-definitions/versions?${params}`, token);
}

export function getMetricSql(
  token: string,
  tenantId: string,
  metricId: string,
): Promise<GeneratedSql> {
  const params = new URLSearchParams({ metric_id: metricId });
  return authedGet(`${base(tenantId)}/metric-definitions/sql?${params}`, token);
}

export function diffMetricDefinitions(
  token: string,
  tenantId: string,
  body: {
    metric_id: string;
    from_version?: number | null;
    to_version?: number | null;
    from_yaml?: string | null;
    to_yaml?: string | null;
  },
): Promise<DiffResponse> {
  return authedRequest(
    "POST",
    `${base(tenantId)}/metric-definitions:diff`,
    token,
    body,
  );
}

export function validateMetricDefinition(
  token: string,
  tenantId: string,
  yaml: string,
): Promise<{ ok: boolean; errors: unknown[]; warnings: unknown[] }> {
  return authedRequest("POST", `${base(tenantId)}/metric-definitions:validate`, token, {
    yaml,
  });
}

export function createMetricDefinition(
  token: string,
  tenantId: string,
  yaml: string,
): Promise<MetricDefinitionDetail> {
  return authedRequest("POST", `${base(tenantId)}/metric-definitions`, token, {
    yaml,
  });
}

export function putMetricDefinitionDraft(
  token: string,
  tenantId: string,
  body: {
    yaml: string;
    expected_version?: number | null;
    expected_revision?: number | null;
  },
): Promise<MetricDefinitionDetail> {
  return authedRequest(
    "PUT",
    `${base(tenantId)}/metric-definitions/draft`,
    token,
    body,
  );
}

export function classifyMetricDefinition(
  token: string,
  tenantId: string,
  body: { yaml: string; previous_version?: number | null },
): Promise<{
  kind: "none" | "non_semantic" | "semantic";
  next_version: number;
  next_revision: number;
  previous_version: number | null;
  previous_revision: number | null;
}> {
  return authedRequest(
    "POST",
    `${base(tenantId)}/metric-definitions:classify`,
    token,
    body,
  );
}

export function activateMetricDefinition(
  token: string,
  tenantId: string,
  metricId: string,
  body: { version?: number | null } = {},
): Promise<MetricDefinitionDetail> {
  const params = new URLSearchParams({ metric_id: metricId });
  return authedRequest(
    "POST",
    `${base(tenantId)}/metric-definitions:activate?${params}`,
    token,
    body,
  );
}

export function repinMetricDefinition(
  token: string,
  tenantId: string,
  metricId: string,
): Promise<MetricDefinitionDetail> {
  const params = new URLSearchParams({ metric_id: metricId });
  return authedRequest(
    "POST",
    `${base(tenantId)}/metric-definitions:repin?${params}`,
    token,
    {},
  );
}

export function archiveMetricDefinition(
  token: string,
  tenantId: string,
  metricId: string,
): Promise<MetricDefinitionDetail> {
  const params = new URLSearchParams({ metric_id: metricId });
  return authedRequest(
    "POST",
    `${base(tenantId)}/metric-definitions:archive?${params}`,
    token,
    {},
  );
}

export type PreviewResponse = {
  rows: Array<Record<string, unknown>>;
  timing_ms: number;
  sql: string;
  grain: string | null;
  diagnostics: Array<Record<string, unknown>>;
  truncated: boolean;
  sampled: boolean;
  executed: boolean;
  metric_id: string | null;
};

export function previewMetricDefinition(
  token: string,
  tenantId: string,
  yaml: string,
): Promise<PreviewResponse> {
  return authedRequest("POST", `${base(tenantId)}/metric-definitions:preview`, token, {
    yaml,
  });
}

export function getMetricSet(token: string, tenantId: string): Promise<MetricSetRead> {
  return authedGet(`${base(tenantId)}/metric-set`, token);
}

export function putMetricSet(
  token: string,
  tenantId: string,
  yaml: string,
): Promise<MetricSetRead> {
  return authedRequest("PUT", `${base(tenantId)}/metric-set`, token, { yaml });
}

export function listDimensionMappings(
  token: string,
  tenantId: string,
): Promise<DimensionMappingSummary[]> {
  return authedGet(`${base(tenantId)}/dimension-mappings`, token);
}

export function getMetricHealth(
  token: string,
  tenantId: string,
): Promise<MetricHealthSummary> {
  return authedGet(`${base(tenantId)}/metric-health`, token);
}

export function listCompileRuns(
  token: string,
  tenantId: string,
): Promise<CompileRun[]> {
  return authedGet(`${base(tenantId)}/metric-compile-runs`, token);
}
