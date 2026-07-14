import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { usePermission } from "@/hooks/use-permission";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import {
  listMetricDefinitions,
  type MetricCatalogItem,
} from "@/features/metrics/api/metric-definitions";
import {
  SourceBadge,
  StatusChip,
  VisibilityBadge,
} from "@/features/metrics/components/metric-badges";

type LoadState =
  | { status: "idle" | "loading" }
  | { status: "ready"; rows: MetricCatalogItem[] }
  | { status: "error"; message: string };

export function MetricsCatalogPage() {
  const { token } = useAuth();
  const { tenant } = useTenant();
  const canManage = usePermission("metrics:manage");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [visibilityFilter, setVisibilityFilter] = useState<string>("all");

  useEffect(() => {
    if (!token || !tenant) return;
    let cancelled = false;
    setState({ status: "loading" });
    listMetricDefinitions(token, tenant.id)
      .then((rows) => {
        if (!cancelled) setState({ status: "ready", rows });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError ? err.message : "Failed to load metrics.";
        setState({ status: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [token, tenant]);

  const filtered = useMemo(() => {
    if (state.status !== "ready") return [];
    const q = search.trim().toLowerCase();
    return state.rows.filter((row) => {
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (sourceFilter !== "all" && row.source !== sourceFilter) return false;
      if (visibilityFilter !== "all" && row.visibility !== visibilityFilter) {
        return false;
      }
      if (!q) return true;
      const hay =
        `${row.name} ${row.metric_id} ${row.description ?? ""} ${row.tags.join(" ")}`.toLowerCase();
      return hay.includes(q);
    });
  }, [state, search, statusFilter, sourceFilter, visibilityFilter]);

  return (
    <main className="bg-background mx-auto min-h-svh max-w-6xl px-6 py-12">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Metrics</h1>
          <p className="text-muted-foreground mt-2 max-w-2xl text-sm">
            Your org&apos;s metric set — standard enrollment, custom definitions, and
            variants. The document is the source of truth.
          </p>
        </div>
        {canManage && (
          <Button asChild analyticsName="metrics_new">
            <Link to="/metrics/new">
              <Plus className="size-4" aria-hidden />
              New metric
            </Link>
          </Button>
        )}
      </header>

      <div className="mb-6 flex flex-wrap gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search
            className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2"
            aria-hidden
          />
          <Input
            className="pl-9"
            placeholder="Search name, id, description…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search metrics"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-36" aria-label="Filter by status">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="broken">Broken</SelectItem>
            <SelectItem value="deprecated">Deprecated</SelectItem>
          </SelectContent>
        </Select>
        <Select value={sourceFilter} onValueChange={setSourceFilter}>
          <SelectTrigger className="w-44" aria-label="Filter by source">
            <SelectValue placeholder="Source" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All sources</SelectItem>
            <SelectItem value="standard">Standard</SelectItem>
            <SelectItem value="standard_customized">Customized</SelectItem>
            <SelectItem value="custom">Custom</SelectItem>
            <SelectItem value="variant">Variant</SelectItem>
          </SelectContent>
        </Select>
        <Select value={visibilityFilter} onValueChange={setVisibilityFilter}>
          <SelectTrigger className="w-36" aria-label="Filter by visibility">
            <SelectValue placeholder="Visibility" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All visibility</SelectItem>
            <SelectItem value="ic">IC</SelectItem>
            <SelectItem value="team">Team</SelectItem>
            <SelectItem value="org">Org</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {state.status === "loading" && (
        <div className="space-y-3" aria-busy="true">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      )}

      {state.status === "error" && (
        <div
          role="alert"
          className="border-destructive/50 bg-destructive/5 text-destructive rounded-lg border p-4 text-sm"
        >
          {state.message}
        </div>
      )}

      {state.status === "ready" && filtered.length === 0 && (
        <div
          className="text-muted-foreground rounded-lg border border-dashed p-10 text-center text-sm"
          data-testid="metrics-empty"
        >
          No metrics match these filters.
          {canManage && (
            <>
              {" "}
              <Link className="text-foreground underline" to="/metrics/new">
                Create one
              </Link>
              .
            </>
          )}
        </div>
      )}

      {state.status === "ready" && filtered.length > 0 && (
        <ul
          className="divide-border divide-y rounded-lg border"
          data-testid="metrics-table"
        >
          {filtered.map((row) => (
            <li
              key={row.metric_id}
              className="hover:bg-muted/40 px-4 py-3 transition-colors"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 space-y-1">
                  <Link
                    to={`/metrics/${encodeURIComponent(row.metric_id)}`}
                    className="text-foreground font-medium hover:underline"
                  >
                    {row.name}
                  </Link>
                  <div className="text-muted-foreground font-mono text-xs">
                    {row.metric_id}
                  </div>
                  {row.description && (
                    <p className="text-muted-foreground line-clamp-2 text-sm">
                      {row.description}
                    </p>
                  )}
                  {row.status === "broken" && row.compile_error && (
                    <p className="text-destructive mt-1 text-sm" role="status">
                      {row.compile_error}
                    </p>
                  )}
                  {row.notices.some((n) => n.notice === "parent_version_available") && (
                    <p className="mt-1 text-xs text-amber-200">
                      Parent version available — review repin on the detail page.
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <SourceBadge source={row.source} extendsId={row.extends} />
                  <StatusChip status={row.status} draftPending={row.draft_pending} />
                  <VisibilityBadge visibility={row.visibility} />
                  {row.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-[11px]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
