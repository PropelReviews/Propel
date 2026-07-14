import { useState } from "react";

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
import { archiveMetricDefinition } from "@/features/metrics/api/metric-definitions";

export function ArchiveMetricDialog({
  open,
  onOpenChange,
  token,
  tenantId,
  metricId,
  dependentCount,
  onArchived,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string;
  tenantId: string;
  metricId: string;
  dependentCount?: number;
  onArchived: () => void;
}) {
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const blocked = (dependentCount ?? 0) > 0;

  async function confirm() {
    if (typed !== metricId) {
      setError("Type the metric id to confirm.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await archiveMetricDefinition(token, tenantId, metricId);
      onOpenChange(false);
      onArchived();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Archive failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Archive {metricId}</DialogTitle>
          <DialogDescription>
            {blocked
              ? `${dependentCount} active metrics reference this — archive is blocked until dependents are archived.`
              : "Archiving removes the metric from the active set. Type the metric id to confirm."}
          </DialogDescription>
        </DialogHeader>
        {!blocked && (
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={metricId}
            className="font-mono"
            aria-label="Confirm metric id"
          />
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
          <Button
            variant="destructive"
            disabled={blocked || saving || typed !== metricId}
            onClick={() => void confirm()}
          >
            {saving ? "Archiving…" : "Archive"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
