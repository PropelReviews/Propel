import { Link } from "react-router-dom";
import { RotateCcw, X } from "lucide-react";

import {
  ChangeFailureChart,
  CycleTimeChart,
  ReviewLatencyChart,
} from "@/components/dora-metric-charts";
import { PrActivityChart } from "@/components/pr-activity-chart";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/providers/auth-provider";
import { AddChartDialog } from "./add-chart-dialog";
import { useMyMetricsLayout } from "./use-my-metrics-layout";
import { getWidget, type MyMetricsWidgetId } from "./widget-catalog";

function WidgetChart({ id, tenantId }: { id: MyMetricsWidgetId; tenantId: string }) {
  switch (id) {
    case "pr-activity":
      return <PrActivityChart tenantId={tenantId} scope="me" />;
    case "cycle-time":
      return <CycleTimeChart tenantId={tenantId} scope="me" />;
    case "review-latency":
      return <ReviewLatencyChart tenantId={tenantId} scope="me" />;
    case "change-failure":
      return <ChangeFailureChart tenantId={tenantId} scope="me" />;
  }
}

/**
 * The individual-contributor dashboard: a default set of personal DORA charts
 * with CloudWatch-style add/remove, persisted per user+workspace.
 */
export function MyMetricsDashboard({
  userId,
  tenantId,
}: {
  userId: string;
  tenantId: string;
}) {
  const { user } = useAuth();
  const { widgets, addWidget, removeWidget, resetWidgets } = useMyMetricsLayout(
    userId,
    tenantId,
  );
  const githubLinked = Boolean(user?.github?.login);

  return (
    <div className="space-y-8">
      {!githubLinked && (
        <Card>
          <CardHeader>
            <CardTitle>Connect GitHub to see your metrics</CardTitle>
            <CardDescription>
              Your charts stay empty until your GitHub account is linked, so we can
              attribute your pull requests and reviews.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" analyticsName="my_metrics_link_github">
              <Link to="/profile">Manage your GitHub connection</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="flex items-center justify-end gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={resetWidgets}
          analyticsName="my_metrics_reset_charts"
        >
          <RotateCcw data-testid="reset-charts-icon" />
          Reset to defaults
        </Button>
        <AddChartDialog visibleWidgets={widgets} onAdd={addWidget} />
      </div>

      {widgets.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No charts on your dashboard</CardTitle>
            <CardDescription>
              You removed every chart. Add one back, or reset to the default DORA view.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        widgets.map((id) => {
          const widget = getWidget(id);
          return (
            <section key={id} aria-label={widget.title}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-medium">{widget.title}</h2>
                  <p className="text-muted-foreground text-sm">{widget.description}</p>
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Remove ${widget.title}`}
                  onClick={() => removeWidget(id)}
                  analyticsName="my_metrics_remove_chart"
                >
                  <X />
                </Button>
              </div>
              <WidgetChart id={id} tenantId={tenantId} />
            </section>
          );
        })
      )}
    </div>
  );
}
