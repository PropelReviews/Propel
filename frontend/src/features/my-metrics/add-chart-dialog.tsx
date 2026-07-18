import { useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { WIDGET_CATALOG, type MyMetricsWidgetId } from "./widget-catalog";

/**
 * CloudWatch-style chart picker: lists catalog widgets not currently on the
 * dashboard and adds one per click. The trigger is disabled when every
 * available chart is already visible.
 */
export function AddChartDialog({
  visibleWidgets,
  onAdd,
}: {
  visibleWidgets: readonly MyMetricsWidgetId[];
  onAdd: (id: MyMetricsWidgetId) => void;
}) {
  const [open, setOpen] = useState(false);
  const available = WIDGET_CATALOG.filter(
    (widget) => !visibleWidgets.includes(widget.id),
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
            Pick a metric to add to your dashboard. Charts show only your own work.
          </DialogDescription>
        </DialogHeader>
        <ul className="space-y-2">
          {available.map((widget) => (
            <li
              key={widget.id}
              className="flex items-center justify-between gap-3 rounded-lg border p-3"
            >
              <div>
                <p className="text-sm font-medium">{widget.title}</p>
                <p className="text-muted-foreground text-xs">{widget.description}</p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                analyticsName="my_metrics_add_chart"
                onClick={() => {
                  onAdd(widget.id);
                  setOpen(false);
                }}
              >
                Add
              </Button>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
