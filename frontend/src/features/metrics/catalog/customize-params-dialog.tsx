import { useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { parse as parseYaml, stringify as stringifyYaml } from "yaml";
import {
  getMetricSet,
  putMetricSet,
  type MetricCatalogItem,
} from "@/features/metrics/api/metric-definitions";

/**
 * Customize declared params on a standard metric by editing the MetricSet doc.
 */
export function CustomizeParamsDialog({
  open,
  onOpenChange,
  metric,
  token,
  tenantId,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  metric: MetricCatalogItem;
  token: string;
  tenantId: string;
  onSaved?: () => void;
}) {
  const [paramsText, setParamsText] = useState(
    JSON.stringify(metric.params_bound ?? {}, null, 2),
  );
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const parsed = JSON.parse(paramsText) as Record<string, unknown>;
      const current = await getMetricSet(token, tenantId);
      const doc =
        current.yaml != null
          ? (parseYaml(current.yaml) as Record<string, unknown>)
          : current.doc;
      const spec = {
        ...((doc.spec as Record<string, unknown>) ?? {}),
      };
      const standard = {
        ...((spec.standard as Record<string, unknown>) ?? { mode: "default_on" }),
      };
      const params = {
        ...((standard.params as Record<string, unknown>) ?? {}),
        [metric.metric_id]: parsed,
      };
      standard.params = params;
      spec.standard = standard;
      doc.spec = spec;
      if (!doc.metadata) doc.metadata = { org: current.org };
      const yaml = stringifyYaml(doc);
      await putMetricSet(token, tenantId, yaml);
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof SyntaxError
            ? "Params must be valid JSON"
            : "Save failed",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Customize {metric.metric_id}</DialogTitle>
          <DialogDescription>
            This changes what <code>{metric.metric_id}</code> means for your whole org
            and recomputes its history. Only declared params belong here — for anything
            else,{" "}
            <Link
              className="underline"
              to={`/metrics/new?extends=${encodeURIComponent(metric.metric_id)}`}
            >
              create a variant
            </Link>
            .
          </DialogDescription>
        </DialogHeader>
        <label className="text-sm">
          <span className="text-muted-foreground mb-1 block">Params JSON</span>
          <textarea
            className="border-input bg-background min-h-32 w-full rounded-lg border p-2 font-mono text-xs"
            value={paramsText}
            onChange={(e) => setParamsText(e.target.value)}
            aria-label="Params JSON"
          />
        </label>
        {error && (
          <p role="alert" className="text-destructive text-sm">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={saving} onClick={() => void save()}>
            {saving ? "Saving…" : "Save to metric set"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ForkPrompt({
  metricId,
  orgSlug,
}: {
  metricId: string;
  orgSlug: string;
}) {
  const localId = metricId.includes(".")
    ? `${orgSlug}.${metricId.split(".").slice(1).join("_")}_variant`
    : `${orgSlug}.variant`;
  return (
    <div
      role="status"
      className="space-y-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm"
      data-testid="fork-prompt"
    >
      <p>
        Standard metrics can&apos;t be edited. Create a variant in your namespace
        instead.
      </p>
      <Button asChild size="sm">
        <Link
          to={`/metrics/new?extends=${encodeURIComponent(metricId)}&id=${encodeURIComponent(localId)}`}
        >
          Create variant ({localId})
        </Link>
      </Button>
    </div>
  );
}

/** Tiny helper kept for story/tests. */
export function ParamsChipInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="font-mono"
    />
  );
}
