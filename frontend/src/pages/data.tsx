import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatCount } from "@/components/charts";
import { ConnectTools } from "@/components/connect-tools";
import { PrActivityChart } from "@/components/pr-activity-chart";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import {
  getIngestionStats,
  listIngestionRuns,
  type IngestionRun,
  type IngestionRunStatus,
  type IngestionStats,
} from "@/lib/ingestion";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

type LoadState =
  | { status: "loading" }
  | {
      status: "ready";
      tenantId: string;
      runs: IngestionRun[];
      stats: IngestionStats;
    }
  | { status: "error"; message: string };

const STATUS_VARIANT: Record<
  IngestionRunStatus,
  "default" | "secondary" | "destructive"
> = {
  success: "secondary",
  running: "default",
  error: "destructive",
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRunDuration(run: IngestionRun): string {
  if (!run.finished_at) return "—";
  const ms = new Date(run.finished_at).getTime() - new Date(run.started_at).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export function DataPage() {
  const { status: authStatus } = useAuth();
  const { tenant, status: tenantStatus, refresh } = useTenant();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (authStatus !== "authenticated" || !tenant) return;

    let cancelled = false;
    (async () => {
      setState({ status: "loading" });
      try {
        const [runs, stats] = await Promise.all([
          listIngestionRuns(tenant.id),
          getIngestionStats(tenant.id),
        ]);
        if (cancelled) return;
        setState({ status: "ready", tenantId: tenant.id, runs, stats });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Could not load ingestion data.";
        setState({ status: "error", message });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authStatus, tenant, tenantStatus, reloadKey]);

  return (
    <main className="bg-background mx-auto min-h-svh max-w-6xl px-6 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight">Data</h1>
        <p className="text-muted-foreground mt-2 max-w-2xl">
          Ingestion activity for your workspace — recent runs and the datapoints landed
          from your connected sources.
        </p>
      </header>

      {authStatus === "loading" ? (
        <LoadingState />
      ) : authStatus !== "authenticated" ? (
        <Card>
          <CardHeader>
            <CardTitle>Sign in required</CardTitle>
            <CardDescription>
              <Link to="/signin" className="underline underline-offset-4">
                Sign in
              </Link>{" "}
              to view ingestion data.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : tenantStatus === "idle" || tenantStatus === "loading" ? (
        <LoadingState />
      ) : tenantStatus === "error" ? (
        <Card>
          <CardHeader>
            <CardTitle>Couldn’t load workspaces</CardTitle>
            <CardDescription>Please try again in a moment.</CardDescription>
          </CardHeader>
        </Card>
      ) : !tenant ? (
        <ConnectTools
          onConnected={() => {
            void refresh();
            setReloadKey((key) => key + 1);
          }}
        />
      ) : state.status === "loading" ? (
        <LoadingState />
      ) : state.status === "error" ? (
        <Card>
          <CardHeader>
            <CardTitle>Couldn’t load data</CardTitle>
            <CardDescription>{state.message}</CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <Loaded tenantId={state.tenantId} runs={state.runs} stats={state.stats} />
      )}
    </main>
  );
}

function LoadingState() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}

function Loaded({
  tenantId,
  runs,
  stats,
}: {
  tenantId: string;
  runs: IngestionRun[];
  stats: IngestionStats;
}) {
  return (
    <div className="space-y-12">
      <section>
        <h2 className="mb-4 text-lg font-medium">Overview</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Datapoints" value={stats.total_datapoints} />
          <StatCard label="Raw records" value={stats.total_raw_records} />
          <StatCard
            label="Sources"
            value={stats.by_source.length}
            hint={stats.by_source.map((s) => s.label).join(", ") || undefined}
          />
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Last run</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {formatTimestamp(stats.last_run_at)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-medium">Pull request activity</h2>
        <PrActivityChart tenantId={tenantId} />
      </section>

      {stats.by_kind.length > 0 && (
        <section>
          <h2 className="mb-4 text-lg font-medium">Datapoints by kind</h2>
          <div className="flex flex-wrap gap-2">
            {stats.by_kind.map((row) => (
              <Badge key={row.label} variant="outline" className="gap-1.5">
                <span className="capitalize">{row.label}</span>
                <span className="text-muted-foreground tabular-nums">
                  {formatCount(row.count)}
                </span>
              </Badge>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-4 text-lg font-medium">Recent runs</h2>
        {runs.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No ingestion runs yet. Runs appear here once a connected source syncs.
          </p>
        ) : (
          <RunsTable runs={runs} />
        )}
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{formatCount(value)}</CardTitle>
      </CardHeader>
      {hint && (
        <CardContent className="text-muted-foreground truncate text-xs">
          {hint}
        </CardContent>
      )}
    </Card>
  );
}

function RunsTable({ runs }: { runs: IngestionRun[] }) {
  return (
    <div className="border-border overflow-x-auto rounded-xl border">
      <table className="w-full text-sm">
        <thead className="text-muted-foreground border-border border-b text-left">
          <tr>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Resource</th>
            <th className="px-4 py-3 text-right font-medium">Records</th>
            <th className="px-4 py-3 text-right font-medium">Datapoints</th>
            <th className="px-4 py-3 font-medium">Started</th>
            <th className="px-4 py-3 font-medium">Duration</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} className="border-border border-b last:border-0">
              <td className="px-4 py-3">
                <Badge variant={STATUS_VARIANT[run.status] ?? "outline"}>
                  {run.status}
                </Badge>
                {run.status === "error" && run.error && (
                  <p
                    className="text-muted-foreground mt-1 max-w-xs truncate text-xs"
                    title={run.error}
                  >
                    {run.error}
                  </p>
                )}
              </td>
              <td className="px-4 py-3">{run.resource_type ?? run.source}</td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCount(run.records_pulled)}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {formatCount(run.datapoints_written)}
              </td>
              <td className="text-muted-foreground px-4 py-3">
                {formatTimestamp(run.started_at)}
              </td>
              <td className="text-muted-foreground px-4 py-3 tabular-nums">
                {formatRunDuration(run)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
