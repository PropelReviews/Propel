import { useEffect, useMemo, useRef, useState } from "react";
import GridLayout, {
  useContainerWidth,
  verticalCompactor,
  type Layout,
} from "react-grid-layout";
import { RotateCcw, X } from "lucide-react";

import {
  clampGranularity,
  MetricFiltersBar,
  MetricFiltersProvider,
  useMetricFilters,
  type Granularity,
  type RelativeRange,
} from "@/components/charts";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  listMetricDefinitions,
  type MetricCatalogItem,
} from "@/features/metrics/api/metric-definitions";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { AddChartDialog } from "./add-chart-dialog";
import {
  GRID_COLS,
  intersectGranularities,
  type DashboardLayoutV2,
} from "./dashboard-layout";
import { MetricValueChart } from "./metric-value-chart";
import { useMyMetricsLayout } from "./use-my-metrics-layout";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

const ROW_HEIGHT = 56;

type CatalogState =
  | { status: "loading" }
  | { status: "ready"; rows: MetricCatalogItem[] }
  | { status: "error"; message: string };

/** Persist filter bar changes into the local/server layout backup. */
function FilterPersistence({
  onChange,
}: {
  onChange: (range: RelativeRange, granularity: Granularity) => void;
}) {
  const { filters } = useMetricFilters();
  const prev = useRef(filters);
  useEffect(() => {
    if (
      prev.current.range === filters.range &&
      prev.current.granularity === filters.granularity
    ) {
      return;
    }
    prev.current = filters;
    onChange(filters.range, filters.granularity);
  }, [filters, onChange]);
  return null;
}

/** Keep the shared granularity inside the intersection of visible metrics. */
function GranularityClamp({ allowed }: { allowed: Granularity[] }) {
  const { filters, setGranularity } = useMetricFilters();
  if (allowed.length > 0 && !allowed.includes(filters.granularity)) {
    setGranularity(allowed[0]);
  }
  return null;
}

function DashboardGrid({
  tenantId,
  catalog,
  layout,
  backupStatus,
  retryBackup,
  setTiles,
  setFilters,
  addWidget,
  removeWidget,
  resetWidgets,
}: {
  tenantId: string;
  catalog: MetricCatalogItem[];
  layout: DashboardLayoutV2;
  backupStatus: "idle" | "saving" | "saved" | "error";
  retryBackup: () => void;
  setTiles: (
    tiles: Array<{ i: string; x: number; y: number; w: number; h: number }>,
  ) => void;
  setFilters: (range: RelativeRange, granularity: Granularity) => void;
  addWidget: (metricId: string) => void;
  removeWidget: (metricId: string) => void;
  resetWidgets: () => void;
}) {
  const { filters, availableGranularities } = useMetricFilters();
  const { width, containerRef, mounted } = useContainerWidth();
  const byId = useMemo(
    () => new Map(catalog.map((row) => [row.metric_id, row])),
    [catalog],
  );

  const visibleMetrics = useMemo(
    () =>
      layout.tiles
        .map((tile) => byId.get(tile.i))
        .filter((row): row is MetricCatalogItem => Boolean(row)),
    [byId, layout.tiles],
  );

  const allowedGranularities = useMemo(() => {
    const metricGrains = intersectGranularities(visibleMetrics);
    return availableGranularities.filter((g) => metricGrains.includes(g));
  }, [availableGranularities, visibleMetrics]);

  const onLayoutChange = (next: Layout) => {
    setTiles(
      next.map((item) => ({
        i: item.i,
        x: item.x,
        y: item.y,
        w: item.w,
        h: item.h,
      })),
    );
  };

  return (
    <div className="space-y-4">
      <FilterPersistence onChange={setFilters} />
      <GranularityClamp allowed={allowedGranularities} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <MetricFiltersBar granularityOptions={allowedGranularities} />
        <div className="flex items-center gap-2">
          {backupStatus === "error" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={retryBackup}
              analyticsName="dashboard_backup_retry"
            >
              Backup failed — retry
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={resetWidgets}
            analyticsName="my_metrics_reset_charts"
          >
            <RotateCcw data-testid="reset-charts-icon" />
            Reset to defaults
          </Button>
          <AddChartDialog
            catalog={catalog}
            tiles={layout.tiles}
            dashboardGranularity={filters.granularity}
            onAdd={addWidget}
          />
        </div>
      </div>

      {layout.tiles.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No charts on your dashboard</CardTitle>
            <CardDescription>
              Add an enrolled metric, or reset to the default workspace view.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div ref={containerRef} className="w-full">
          {mounted && width > 0 ? (
            <GridLayout
              className="layout"
              layout={layout.tiles}
              width={width}
              gridConfig={{
                cols: GRID_COLS,
                rowHeight: ROW_HEIGHT,
                margin: [16, 16],
              }}
              dragConfig={{
                handle: ".dashboard-tile-drag",
              }}
              compactor={verticalCompactor}
              onLayoutChange={onLayoutChange}
            >
              {layout.tiles.map((tile) => {
                const metric = byId.get(tile.i);
                const chartHeight = Math.max(160, tile.h * ROW_HEIGHT - 88);
                return (
                  <div
                    key={tile.i}
                    className="bg-card flex h-full flex-col overflow-hidden rounded-xl border shadow-sm"
                    data-testid={`dashboard-tile-${tile.i}`}
                    aria-label={metric?.name ?? tile.i}
                  >
                    <div className="flex items-start justify-between gap-2 px-4 pt-3">
                      <div className="min-w-0">
                        <button
                          type="button"
                          className="dashboard-tile-drag text-muted-foreground hover:text-foreground mb-1 cursor-grab text-[10px] font-medium tracking-wide uppercase"
                          aria-label={`Drag ${metric?.name ?? tile.i}`}
                        >
                          Drag to move
                        </button>
                        <h2 className="truncate text-base font-medium">
                          {metric?.name ?? tile.i}
                        </h2>
                        {metric?.description ? (
                          <p className="text-muted-foreground line-clamp-2 text-xs">
                            {metric.description}
                          </p>
                        ) : null}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        aria-label={`Remove ${metric?.name ?? tile.i}`}
                        onClick={() => removeWidget(tile.i)}
                        analyticsName="my_metrics_remove_chart"
                      >
                        <X />
                      </Button>
                    </div>
                    <div className="min-h-0 flex-1 px-2 pb-2">
                      {metric ? (
                        <MetricValueChart
                          tenantId={tenantId}
                          metric={metric}
                          height={chartHeight}
                        />
                      ) : (
                        <p className="text-muted-foreground p-4 text-sm">
                          This metric is no longer enrolled. Remove the tile or
                          re-enroll it in Metrics.
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </GridLayout>
          ) : null}
        </div>
      )}
    </div>
  );
}

function DashboardShell({
  userId,
  tenantId,
  catalog,
}: {
  userId: string;
  tenantId: string;
  catalog: MetricCatalogItem[];
}) {
  const { token } = useAuth();
  const availableIds = useMemo(
    () =>
      catalog
        .filter((row) => row.status === "active" && row.enrolled)
        .map((row) => row.metric_id),
    [catalog],
  );

  const {
    layout,
    hydrated,
    backupStatus,
    retryBackup,
    setTiles,
    setFilters,
    addWidget,
    removeWidget,
    resetWidgets,
  } = useMyMetricsLayout(userId, tenantId, token, availableIds);

  if (!hydrated || !layout) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Loading dashboard…</CardTitle>
          <CardDescription>Restoring your saved layout.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const initialRange: RelativeRange = layout.range ?? "quarter";
  const initialGranularity: Granularity = clampGranularity(
    initialRange,
    layout.granularity ?? "weekly",
  );

  return (
    <MetricFiltersProvider
      initialRange={initialRange}
      initialGranularity={initialGranularity}
    >
      <DashboardGrid
        tenantId={tenantId}
        catalog={catalog}
        layout={layout}
        backupStatus={backupStatus}
        retryBackup={retryBackup}
        setTiles={setTiles}
        setFilters={setFilters}
        addWidget={addWidget}
        removeWidget={removeWidget}
        resetWidgets={resetWidgets}
      />
    </MetricFiltersProvider>
  );
}

/**
 * Workspace metrics dashboard: catalog-driven tiles, shared filters, and
 * local-first layout with debounced server backup.
 */
export function MyMetricsDashboard({
  userId,
  tenantId,
}: {
  userId: string;
  tenantId: string;
}) {
  const { token } = useAuth();
  const [catalog, setCatalog] = useState<CatalogState>({ status: "loading" });

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    void (async () => {
      try {
        const rows = await listMetricDefinitions(token, tenantId, {
          includeDrafts: false,
          includeBroken: false,
        });
        if (!cancelled) setCatalog({ status: "ready", rows });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Could not load metrics.";
        setCatalog({ status: "error", message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId]);

  if (catalog.status === "loading") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Loading metrics…</CardTitle>
          <CardDescription>Fetching your enrolled metric catalog.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (catalog.status === "error") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Couldn’t load metrics</CardTitle>
          <CardDescription>{catalog.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return <DashboardShell userId={userId} tenantId={tenantId} catalog={catalog.rows} />;
}
