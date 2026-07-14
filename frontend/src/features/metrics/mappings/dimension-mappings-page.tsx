import { useEffect, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import {
  listDimensionMappings,
  type DimensionMappingSummary,
} from "@/features/metrics/api/metric-definitions";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; rows: DimensionMappingSummary[] }
  | { status: "error"; message: string };

export function DimensionMappingsPage() {
  const { token } = useAuth();
  const { tenant } = useTenant();
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    if (!token || !tenant) return;
    let cancelled = false;
    listDimensionMappings(token, tenant.id)
      .then((rows) => {
        if (!cancelled) setState({ status: "ready", rows });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load mappings.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [token, tenant]);

  return (
    <main className="bg-background mx-auto min-h-svh max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Dimension mappings</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Virtual dimensions derived from field value maps. They appear in the builder
          catalog with a mapping icon.
        </p>
      </header>

      {state.status === "loading" && <Skeleton className="h-24 w-full" />}
      {state.status === "error" && (
        <div role="alert" className="text-destructive text-sm">
          {state.message}
        </div>
      )}
      {state.status === "ready" && state.rows.length === 0 && (
        <p
          className="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm"
          data-testid="mappings-empty"
        >
          No dimension mappings yet. Push a DimensionMapping document or add one via the
          API.
        </p>
      )}
      {state.status === "ready" && state.rows.length > 0 && (
        <ul className="divide-border divide-y rounded-lg border">
          {state.rows.map((row) => (
            <li key={row.mapping_id} className="px-4 py-3 text-sm">
              <div className="font-mono font-medium">{row.mapping_id}</div>
              <div className="text-muted-foreground mt-1 text-xs">
                {row.entity}.{row.from_field} → {row.to_dimension} · {row.status} · v
                {row.version}
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
