import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import {
  getMetricHealth,
  type MetricHealthSummary,
} from "@/features/metrics/api/metric-definitions";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; health: MetricHealthSummary }
  | { status: "error"; message: string };

/**
 * Metric compile/run health, embedded as a section of the Workspace page
 * (it used to be its own /settings/metric-health page).
 */
export function MetricHealthSection() {
  const { token } = useAuth();
  const { tenant } = useTenant();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    if (!token || !tenant) return;
    let cancelled = false;
    getMetricHealth(token, tenant.id)
      .then((health) => {
        if (!cancelled) setState({ status: "ready", health });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load health.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [token, tenant]);

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-lg font-medium">Metric health</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Compile runs, broken metrics, and parent-version notices.
        </p>
      </div>

      {state.status === "loading" && <Skeleton className="h-32 w-full" />}
      {state.status === "error" && (
        <div role="alert" className="text-destructive text-sm">
          {state.message}
        </div>
      )}
      {state.status === "ready" && (
        <div className="space-y-8">
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat label="Broken" value={state.health.broken_count} />
            <Stat label="Notices" value={state.health.notice_count} />
            <Stat
              label="Parent bumps"
              value={state.health.open_parent_version_notices}
            />
          </div>

          <div>
            <h3 className="mb-3 font-medium">Broken metrics</h3>
            {state.health.broken_metrics.length === 0 ? (
              <p className="text-muted-foreground text-sm">None.</p>
            ) : (
              <ul className="divide-border divide-y rounded-lg border">
                {state.health.broken_metrics.map((m) => (
                  <li key={m.metric_id} className="px-4 py-3 text-sm">
                    <Link
                      className="font-mono hover:underline"
                      to={`/metrics/${encodeURIComponent(m.metric_id)}`}
                    >
                      {m.metric_id}
                    </Link>
                    <span className="text-muted-foreground"> · v{m.version}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-3 font-medium">Recent compile runs</h3>
            {state.health.recent_compile_runs.length === 0 ? (
              <p className="text-muted-foreground text-sm">No runs yet.</p>
            ) : (
              <ul className="divide-border divide-y rounded-lg border">
                {state.health.recent_compile_runs.map((run) => (
                  <li
                    key={run.id}
                    className="flex flex-wrap justify-between gap-2 px-4 py-3 text-sm"
                  >
                    <span>
                      <span className="font-medium">{run.status}</span>
                      <span className="text-muted-foreground"> · {run.trigger}</span>
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {new Date(run.started_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border p-4">
      <div className="text-muted-foreground text-xs tracking-wide uppercase">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
