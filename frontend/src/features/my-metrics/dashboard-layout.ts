import type { Granularity, RelativeRange } from "@/components/charts";

/** One metric tile on the workspace dashboard grid. */
export type DashboardTile = {
  /** Metric id (react-grid-layout item key). */
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

export type DashboardLayoutV2 = {
  version: 2;
  range?: RelativeRange;
  granularity?: Granularity;
  tiles: DashboardTile[];
};

export const DEFAULT_TILE_W = 6;
export const DEFAULT_TILE_H = 4;
export const GRID_COLS = 12;

/** Preferred defaults when those metrics are enrolled and active. */
export const PREFERRED_DEFAULT_METRIC_IDS = [
  "propel.cycle_time",
  "propel.review_latency",
  "propel.change_failure_rate",
  "propel.deployment_frequency",
  "propel.merged_prs",
] as const;

export function myMetricsStorageKey(userId: string, tenantId: string): string {
  return `propel_my_metrics:${userId}:${tenantId}`;
}

export function tilesFromMetricIds(metricIds: readonly string[]): DashboardTile[] {
  return metricIds.map((id, index) => ({
    i: id,
    x: (index % 2) * DEFAULT_TILE_W,
    y: Math.floor(index / 2) * DEFAULT_TILE_H,
    w: DEFAULT_TILE_W,
    h: DEFAULT_TILE_H,
  }));
}

export function defaultLayoutForMetrics(
  availableMetricIds: readonly string[],
): DashboardLayoutV2 {
  const available = new Set(availableMetricIds);
  const preferred = PREFERRED_DEFAULT_METRIC_IDS.filter((id) => available.has(id));
  const ids =
    preferred.length > 0
      ? preferred
      : availableMetricIds.slice(0, Math.min(4, availableMetricIds.length));
  return {
    version: 2,
    range: "quarter",
    granularity: "weekly",
    tiles: tilesFromMetricIds(ids),
  };
}

function isTile(value: unknown): value is DashboardTile {
  if (!value || typeof value !== "object") return false;
  const tile = value as Record<string, unknown>;
  return (
    typeof tile.i === "string" &&
    tile.i.length > 0 &&
    typeof tile.x === "number" &&
    typeof tile.y === "number" &&
    typeof tile.w === "number" &&
    typeof tile.h === "number" &&
    tile.w >= 1 &&
    tile.h >= 1
  );
}

/** Parse a stored layout, migrating legacy string[] widget lists. */
export function parseStoredLayout(raw: string | null): DashboardLayoutV2 | null {
  if (raw === null) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      const ids = [
        ...new Set(
          parsed.filter((id): id is string => typeof id === "string" && id.length > 0),
        ),
      ];
      return {
        version: 2,
        range: "quarter",
        granularity: "weekly",
        tiles: tilesFromMetricIds(ids),
      };
    }
    if (!parsed || typeof parsed !== "object") return null;
    const obj = parsed as Record<string, unknown>;
    if (obj.version !== 2 || !Array.isArray(obj.tiles)) return null;
    const tiles = obj.tiles.filter(isTile);
    // Drop duplicates while preserving order.
    const seen = new Set<string>();
    const unique = tiles.filter((tile) => {
      if (seen.has(tile.i)) return false;
      seen.add(tile.i);
      return true;
    });
    return {
      version: 2,
      range: typeof obj.range === "string" ? (obj.range as RelativeRange) : undefined,
      granularity:
        typeof obj.granularity === "string"
          ? (obj.granularity as Granularity)
          : undefined,
      tiles: unique,
    };
  } catch {
    return null;
  }
}

export function loadLocalLayout(storageKey: string): DashboardLayoutV2 | null {
  try {
    return parseStoredLayout(localStorage.getItem(storageKey));
  } catch {
    return null;
  }
}

export function saveLocalLayout(storageKey: string, layout: DashboardLayoutV2): void {
  try {
    localStorage.setItem(storageKey, JSON.stringify(layout));
  } catch {
    // Storage full/unavailable — in-memory layout still works this session.
  }
}

/** Map catalog grain names (day/week/month) onto filter Granularity. */
export function catalogGrainToGranularity(grain: string): Granularity | null {
  if (grain === "day") return "daily";
  if (grain === "week") return "weekly";
  if (grain === "month") return "monthly";
  return null;
}

export function granularitiesForMetric(
  grains: readonly string[] | undefined,
): Granularity[] {
  if (!grains || grains.length === 0) {
    return ["daily", "weekly", "monthly"];
  }
  const out: Granularity[] = [];
  for (const grain of grains) {
    const g = catalogGrainToGranularity(grain);
    if (g && !out.includes(g)) out.push(g);
  }
  return out.length > 0 ? out : ["daily", "weekly", "monthly"];
}

/** Intersection of granularities supported by every visible metric. */
export function intersectGranularities(
  metrics: ReadonlyArray<{ grains?: string[] }>,
): Granularity[] {
  if (metrics.length === 0) return ["daily", "weekly", "monthly"];
  let current: Granularity[] | null = null;
  for (const metric of metrics) {
    const next = granularitiesForMetric(metric.grains);
    current = current ? current.filter((g) => next.includes(g)) : [...next];
  }
  return current && current.length > 0 ? current : ["daily", "weekly", "monthly"];
}
