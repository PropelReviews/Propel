import { useMemo, useState } from "react";
import { Plus } from "lucide-react";

import type { Granularity } from "@/components/charts";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { MetricCatalogItem } from "@/features/metrics/api/metric-definitions";

import { granularitiesForMetric, type DashboardTile } from "./dashboard-layout";

/**
 * CloudWatch-style chart picker driven by enrolled metric definitions.
 * Metrics incompatible with the dashboard's shared granularity are disabled.
 */
export function AddChartDialog({
  catalog,
  tiles,
  dashboardGranularity,
  onAdd,
}: {
  catalog: readonly MetricCatalogItem[];
  tiles: readonly DashboardTile[];
  dashboardGranularity: Granularity;
  onAdd: (metricId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const visible = useMemo(() => new Set(tiles.map((tile) => tile.i)), [tiles]);

  const available = useMemo(
    () =>
      catalog.filter(
        (metric) =>
          metric.status === "active" &&
          metric.enrolled &&
          !visible.has(metric.metric_id),
      ),
    [catalog, visible],
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          disabled={available.length === 0}
          analyticsName="my_metrics_add_chart_open"
        >
          <Plus data-testid="add-chart-icon" />
          Add chart
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a chart</DialogTitle>
          <DialogDescription>
            Pick an enrolled workspace metric. Charts share this dashboard&apos;s
            timeframe and granularity.
          </DialogDescription>
        </DialogHeader>
        <ul className="max-h-80 space-y-2 overflow-y-auto">
          {available.map((metric) => {
            const supported = granularitiesForMetric(metric.grains);
            const compatible = supported.includes(dashboardGranularity);
            return (
              <li
                key={metric.metric_id}
                className="flex items-center justify-between gap-3 rounded-lg border p-3"
              >
                <div>
                  <p className="text-sm font-medium">{metric.name}</p>
                  <p className="text-muted-foreground text-xs">
                    {metric.description ?? metric.metric_id}
                  </p>
                  {!compatible && (
                    <p className="text-destructive mt-1 text-xs">
                      Does not support {dashboardGranularity} granularity with the
                      current dashboard filters.
                    </p>
                  )}
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={!compatible}
                  analyticsName="my_metrics_add_chart"
                  onClick={() => {
                    onAdd(metric.metric_id);
                    setOpen(false);
                  }}
                >
                  Add
                </Button>
              </li>
            );
          })}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
