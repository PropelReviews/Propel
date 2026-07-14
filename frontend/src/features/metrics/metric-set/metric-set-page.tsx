import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { usePermission } from "@/hooks/use-permission";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";
import {
  getMetricSet,
  putMetricSet,
  type MetricSetRead,
} from "@/features/metrics/api/metric-definitions";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; set: MetricSetRead }
  | { status: "error"; message: string };

export function MetricSetSettingsPage() {
  const { token } = useAuth();
  const { tenant } = useTenant();
  const canManage = usePermission("metrics:manage");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [draftYaml, setDraftYaml] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveOk, setSaveOk] = useState(false);

  useEffect(() => {
    if (!token || !tenant) return;
    let cancelled = false;
    getMetricSet(token, tenant.id)
      .then((set) => {
        if (cancelled) return;
        setState({ status: "ready", set });
        setDraftYaml(
          set.yaml ??
            [
              "apiVersion: propel/v1",
              "kind: MetricSet",
              "metadata:",
              `  org: ${set.org}`,
              "spec:",
              "  standard:",
              "    mode: default_on",
            ].join("\n"),
        );
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Failed to load metric set.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [token, tenant]);

  async function onSave() {
    if (!token || !tenant) return;
    setSaving(true);
    setSaveError(null);
    setSaveOk(false);
    try {
      const updated = await putMetricSet(token, tenant.id, draftYaml);
      setState({ status: "ready", set: updated });
      setDraftYaml(updated.yaml ?? draftYaml);
      setSaveOk(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="bg-background mx-auto min-h-svh max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Metric set</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Enable or disable standard metrics and bind params. This updates your metric
          set — enrollment-only changes do not require recompiling every metric.
        </p>
      </header>

      {state.status === "loading" && <Skeleton className="h-48 w-full" />}
      {state.status === "error" && (
        <div role="alert" className="text-destructive text-sm">
          {state.message}
        </div>
      )}
      {state.status === "ready" && (
        <div className="space-y-4">
          <p className="text-muted-foreground text-xs">
            Status: {state.set.status}
            {state.set.version != null ? ` · v${state.set.version}` : ""}
          </p>
          {canManage ? (
            <textarea
              className="border-input bg-background focus-visible:ring-ring/50 min-h-64 w-full rounded-lg border p-3 font-mono text-sm outline-none focus-visible:ring-3"
              value={draftYaml}
              onChange={(e) => setDraftYaml(e.target.value)}
              spellCheck={false}
              aria-label="MetricSet YAML"
            />
          ) : (
            <CodeBlock code={draftYaml || "# (implicit default_on MetricSet)"} />
          )}
          {canManage && (
            <div className="flex items-center gap-3">
              <Button
                analyticsName="metric_set_save"
                disabled={saving}
                onClick={() => void onSave()}
              >
                {saving ? "Saving…" : "Save metric set"}
              </Button>
              {saveOk && <span className="text-muted-foreground text-sm">Saved.</span>}
              {saveError && (
                <span role="alert" className="text-destructive text-sm">
                  {saveError}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
