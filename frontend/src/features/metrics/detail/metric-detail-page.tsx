import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api";
import { usePermission } from "@/hooks/use-permission";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import {
  diffMetricDefinitions,
  getMetricDefinition,
  getMetricSql,
  listMetricVersions,
  type DiffResponse,
  type MetricDefinitionDetail,
  type MetricVersion,
} from "@/features/metrics/api/metric-definitions";
import {
  AdvancedBanner,
  StatusChip,
  VisibilityBadge,
} from "@/features/metrics/components/metric-badges";
import {
  isAdvancedDocument,
  parseYamlLoose,
} from "@/features/metrics/document/advanced";

type LoadState =
  | { status: "loading" }
  | {
      status: "ready";
      detail: MetricDefinitionDetail;
      versions: MetricVersion[];
    }
  | { status: "error"; message: string };

export function MetricDetailPage() {
  const { metricId: rawId } = useParams<{ metricId: string }>();
  const metricId = rawId ? decodeURIComponent(rawId) : "";
  const { token } = useAuth();
  const { tenant } = useTenant();
  const canManage = usePermission("metrics:manage");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [defView, setDefView] = useState<"authored" | "resolved" | "sql">("authored");
  const [sql, setSql] = useState<string | null>(null);
  const [sqlError, setSqlError] = useState<string | null>(null);
  const [diffFrom, setDiffFrom] = useState<number | null>(null);
  const [diffTo, setDiffTo] = useState<number | null>(null);
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !tenant || !metricId) return;
    let cancelled = false;
    setState({ status: "loading" });
    Promise.all([
      getMetricDefinition(token, tenant.id, metricId),
      listMetricVersions(token, tenant.id, metricId),
    ])
      .then(([detail, versions]) => {
        if (cancelled) return;
        setState({ status: "ready", detail, versions });
        if (versions.length >= 2) {
          setDiffTo(versions[0]?.version ?? null);
          setDiffFrom(versions[1]?.version ?? null);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load metric.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [token, tenant, metricId]);

  useEffect(() => {
    if (!token || !tenant || !metricId || defView !== "sql") return;
    let cancelled = false;
    setSqlError(null);
    getMetricSql(token, tenant.id, metricId)
      .then((res) => {
        if (!cancelled) setSql(res.sql);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSql(null);
        setSqlError(
          err instanceof ApiError ? err.message : "Generated SQL unavailable.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token, tenant, metricId, defView]);

  const advanced = useMemo(() => {
    if (state.status !== "ready") return false;
    const resolved = state.detail.resolved_json;
    if (resolved && isAdvancedDocument(resolved as never)) return true;
    const loose = parseYamlLoose(state.detail.yaml);
    return loose ? isAdvancedDocument(loose as never) : false;
  }, [state]);

  async function runDiff() {
    if (!token || !tenant || diffFrom == null || diffTo == null) return;
    setDiffError(null);
    try {
      const result = await diffMetricDefinitions(token, tenant.id, {
        metric_id: metricId,
        from_version: diffFrom,
        to_version: diffTo,
      });
      setDiff(result);
    } catch (err) {
      setDiff(null);
      setDiffError(err instanceof ApiError ? err.message : "Diff failed.");
    }
  }

  if (state.status === "loading") {
    return (
      <main className="mx-auto max-w-6xl px-6 py-12">
        <Skeleton className="mb-4 h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </main>
    );
  }

  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-6xl px-6 py-12">
        <div role="alert" className="text-destructive text-sm">
          {state.message}
        </div>
        <Button asChild variant="outline" className="mt-4">
          <Link to="/metrics">Back to catalog</Link>
        </Button>
      </main>
    );
  }

  const { detail, versions } = state;
  const meta = (detail.resolved_json?.metadata ?? {}) as Record<string, unknown>;
  const spec = (detail.resolved_json?.spec ?? {}) as Record<string, unknown>;
  const name =
    (typeof meta.name === "string" && meta.name) ||
    detail.metric_id.split(".").slice(1).join(".") ||
    detail.metric_id;
  const parentNotice = detail.notices.find(
    (n) => n.notice === "parent_version_available",
  );

  return (
    <main className="bg-background mx-auto min-h-svh max-w-6xl px-6 py-12">
      <div className="text-muted-foreground mb-4 text-sm">
        <Link to="/metrics" className="hover:text-foreground">
          Metrics
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground font-mono">{detail.metric_id}</span>
      </div>

      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">{name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip status={detail.status} />
            <VisibilityBadge visibility={String(spec.visibility ?? "")} />
            <span className="text-muted-foreground text-xs">
              v{detail.version} · rev {detail.revision}
            </span>
          </div>
        </div>
        {canManage && !advanced && (
          <Button asChild variant="outline" analyticsName="metrics_edit">
            <Link to={`/metrics/${encodeURIComponent(metricId)}/edit`}>Edit</Link>
          </Button>
        )}
      </header>

      {advanced && (
        <div className="mb-6">
          <AdvancedBanner />
        </div>
      )}

      {parentNotice && (
        <div
          role="status"
          className="mb-6 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm"
        >
          A newer parent version is available.
          {canManage && (
            <span className="text-muted-foreground">
              {" "}
              Use Repin from the Overview actions once the builder flow lands (M5.4).
            </span>
          )}
        </div>
      )}

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="definition">Definition</TabsTrigger>
          <TabsTrigger value="preview" disabled>
            Preview
          </TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6 space-y-4">
          {typeof meta.description === "string" && (
            <p className="text-muted-foreground text-sm">{meta.description}</p>
          )}
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Owner</dt>
              <dd>{String(meta.owner ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Entity</dt>
              <dd className="font-mono">{String(spec.entity ?? "—")}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Content hash</dt>
              <dd className="font-mono text-xs break-all">
                {detail.content_hash ?? "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Parent pin</dt>
              <dd className="font-mono text-xs">
                {detail.parent_pin ? JSON.stringify(detail.parent_pin) : "—"}
              </dd>
            </div>
          </dl>
          <div>
            <h2 className="mb-2 text-sm font-medium">Visibility</h2>
            <p className="text-muted-foreground text-sm">
              {visibilityCopy(String(spec.visibility ?? ""))}
            </p>
          </div>
        </TabsContent>

        <TabsContent value="definition" className="mt-6 space-y-4">
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["authored", "Authored YAML"],
                ["resolved", "Resolved YAML"],
                ["sql", "Generated SQL"],
              ] as const
            ).map(([key, label]) => (
              <Button
                key={key}
                size="sm"
                variant={defView === key ? "default" : "outline"}
                onClick={() => setDefView(key)}
              >
                {label}
              </Button>
            ))}
          </div>
          {defView === "authored" && <CodeBlock code={detail.yaml} />}
          {defView === "resolved" && (
            <CodeBlock
              code={
                detail.resolved_json
                  ? JSON.stringify(detail.resolved_json, null, 2)
                  : "# No resolved JSON stored yet"
              }
            />
          )}
          {defView === "sql" && (
            <>
              {sqlError && (
                <p role="status" className="text-muted-foreground text-sm">
                  {sqlError}
                </p>
              )}
              {sql && <CodeBlock code={sql} />}
            </>
          )}
        </TabsContent>

        <TabsContent value="preview" className="mt-6">
          <p className="text-muted-foreground text-sm">Preview arrives in M5.3.</p>
        </TabsContent>

        <TabsContent value="versions" className="mt-6 space-y-4">
          <ul className="divide-border divide-y rounded-lg border">
            {versions.map((v) => (
              <li
                key={`${v.org_id}-${v.version}`}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"
              >
                <div>
                  <span className="font-medium">v{v.version}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    · rev {v.revision} · {v.status}
                  </span>
                </div>
                <span className="text-muted-foreground text-xs">
                  {v.created_at ? new Date(v.created_at).toLocaleString() : "—"}
                </span>
              </li>
            ))}
          </ul>

          <div className="flex flex-wrap items-end gap-3">
            <label className="text-sm">
              <span className="text-muted-foreground mb-1 block">From</span>
              <select
                className="border-input bg-background h-8 rounded-md border px-2 text-sm"
                value={diffFrom ?? ""}
                onChange={(e) => setDiffFrom(Number(e.target.value))}
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="text-muted-foreground mb-1 block">To</span>
              <select
                className="border-input bg-background h-8 rounded-md border px-2 text-sm"
                value={diffTo ?? ""}
                onChange={(e) => setDiffTo(Number(e.target.value))}
              >
                {versions.map((v) => (
                  <option key={v.version} value={v.version}>
                    v{v.version}
                  </option>
                ))}
              </select>
            </label>
            <Button size="sm" onClick={() => void runDiff()}>
              Compare
            </Button>
          </div>
          {diffError && (
            <p role="alert" className="text-destructive text-sm">
              {diffError}
            </p>
          )}
          {diff && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Structural diff</h3>
              {diff.summary.length === 0 ? (
                <p className="text-muted-foreground text-sm">No differences.</p>
              ) : (
                <ul className="bg-muted/40 space-y-1 rounded-lg p-3 font-mono text-xs">
                  {diff.summary.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </main>
  );
}

function visibilityCopy(visibility: string): string {
  switch (visibility) {
    case "ic":
      return "Surfaced to each individual about their own work; appears in team/org rollups only if the individual opts in.";
    case "team":
      return "Visible to the team. Person-dimension breakdowns still respect individual opt-in for IC rows.";
    case "org":
      return "Visible across the organization. Prefer IC for person-level flow metrics.";
    default:
      return "Visibility is declared on the metric document.";
  }
}
