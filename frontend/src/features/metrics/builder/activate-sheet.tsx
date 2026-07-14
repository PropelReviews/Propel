import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useState } from "react";

import { ApiError } from "@/lib/api";
import {
  activateMetricDefinition,
  classifyMetricDefinition,
  createMetricDefinition,
  diffMetricDefinitions,
  putMetricDefinitionDraft,
  type DiffResponse,
} from "@/features/metrics/api/metric-definitions";
import { documentToYaml } from "@/features/metrics/document/yaml-io";

export function ActivateReviewSheet({
  open,
  onOpenChange,
  token,
  tenantId,
  doc,
  storeVersion,
  storeRevision,
  onStoreMeta,
  onActivated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string;
  tenantId: string;
  doc: Record<string, unknown>;
  storeVersion: number | null;
  storeRevision: number | null;
  onStoreMeta: (version: number, revision: number) => void;
  onActivated: (metricId: string) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<string | null>(null);
  const [nextVersion, setNextVersion] = useState<number | null>(null);
  const [diff, setDiff] = useState<DiffResponse | null>(null);

  async function prepare() {
    setError(null);
    setLoading(true);
    try {
      const yaml = documentToYaml(doc);
      const classification = await classifyMetricDefinition(token, tenantId, {
        yaml,
      });
      setKind(classification.kind);
      setNextVersion(classification.next_version);
      if (classification.previous_version != null) {
        const d = await diffMetricDefinitions(token, tenantId, {
          metric_id: String((doc.metadata as { id?: string })?.id ?? ""),
          from_version: classification.previous_version,
          to_yaml: yaml,
        });
        setDiff(d);
      } else {
        setDiff({
          changes: [],
          summary: ["New metric"],
          from_resolved: null,
          to_resolved: null,
        });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Classify failed");
    } finally {
      setLoading(false);
    }
  }

  // Load classification when opened
  useState(() => {
    if (open) void prepare();
  });

  async function confirm() {
    setLoading(true);
    setError(null);
    try {
      const yaml = documentToYaml(doc);
      const mid = String((doc.metadata as { id?: string })?.id ?? "");
      if (storeVersion == null) {
        const created = await createMetricDefinition(token, tenantId, yaml);
        onStoreMeta(created.version, created.revision);
      } else {
        const updated = await putMetricDefinitionDraft(token, tenantId, {
          yaml,
          expected_version: storeVersion,
          expected_revision: storeRevision,
        });
        onStoreMeta(updated.version, updated.revision);
      }
      const classification = await classifyMetricDefinition(token, tenantId, {
        yaml,
      });
      await activateMetricDefinition(token, tenantId, mid, {
        version: classification.next_version,
      });
      onOpenChange(false);
      onActivated(mid);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Activate failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (next) void prepare();
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Activate metric</DialogTitle>
          <DialogDescription>
            Review the change class before activating. Semantic edits mint a new
            version and recompute history; display-only edits bump a revision.
          </DialogDescription>
        </DialogHeader>
        {loading && !kind && (
          <p className="text-muted-foreground text-sm">Classifying…</p>
        )}
        {kind && (
          <div className="space-y-3 text-sm">
            <p>
              <span className="font-medium">Classification:</span>{" "}
              {kind === "semantic"
                ? `Semantic change → version ${nextVersion}, full history recompute`
                : kind === "non_semantic"
                  ? `Display-only change → revision bump, no recompute`
                  : "No change"}
            </p>
            {diff && (
              <ul className="bg-muted/40 max-h-48 space-y-1 overflow-auto rounded-lg p-3 font-mono text-xs">
                {(diff.summary.length ? diff.summary : ["(no structural diff)"]).map(
                  (line) => (
                    <li key={line}>{line}</li>
                  ),
                )}
              </ul>
            )}
          </div>
        )}
        {error && (
          <p role="alert" className="text-destructive text-sm">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={loading || !kind} onClick={() => void confirm()}>
            {loading ? "Working…" : "Confirm activate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
