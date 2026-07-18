import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  defaultLayoutForMetrics,
  granularitiesForMetric,
  intersectGranularities,
  loadLocalLayout,
  myMetricsStorageKey,
  parseStoredLayout,
  tilesFromMetricIds,
} from "./dashboard-layout";

const KEY = myMetricsStorageKey("user-1", "tenant-1");
const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
    clear: () => store.clear(),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("myMetricsStorageKey", () => {
  it("is scoped per user and workspace", () => {
    expect(KEY).toBe("propel_my_metrics:user-1:tenant-1");
    expect(myMetricsStorageKey("user-2", "tenant-1")).not.toBe(KEY);
  });
});

describe("parseStoredLayout", () => {
  it("migrates legacy string[] layouts into tiles", () => {
    const layout = parseStoredLayout(
      JSON.stringify(["propel.cycle_time", "propel.merged_prs"]),
    );
    expect(layout?.version).toBe(2);
    expect(layout?.tiles.map((t) => t.i)).toEqual([
      "propel.cycle_time",
      "propel.merged_prs",
    ]);
  });

  it("preserves a versioned layout and drops duplicate tiles", () => {
    const layout = parseStoredLayout(
      JSON.stringify({
        version: 2,
        range: "month",
        granularity: "daily",
        tiles: [
          { i: "propel.cycle_time", x: 0, y: 0, w: 6, h: 4 },
          { i: "propel.cycle_time", x: 6, y: 0, w: 6, h: 4 },
          { i: "propel.merged_prs", x: 0, y: 4, w: 12, h: 3 },
        ],
      }),
    );
    expect(layout?.tiles.map((t) => t.i)).toEqual([
      "propel.cycle_time",
      "propel.merged_prs",
    ]);
    expect(layout?.range).toBe("month");
  });

  it("treats an empty tile list as intentional", () => {
    expect(parseStoredLayout(JSON.stringify({ version: 2, tiles: [] }))).toEqual({
      version: 2,
      range: undefined,
      granularity: undefined,
      tiles: [],
    });
  });

  it("returns null for malformed payloads", () => {
    expect(parseStoredLayout("{not json")).toBeNull();
    expect(parseStoredLayout(JSON.stringify({ version: 1, tiles: [] }))).toBeNull();
  });
});

describe("loadLocalLayout", () => {
  it("returns null when nothing is stored", () => {
    expect(loadLocalLayout(KEY)).toBeNull();
  });

  it("loads a stored layout", () => {
    store.set(KEY, JSON.stringify({ version: 2, tiles: tilesFromMetricIds(["a"]) }));
    expect(loadLocalLayout(KEY)?.tiles[0]?.i).toBe("a");
  });
});

describe("defaultLayoutForMetrics", () => {
  it("prefers known good metric ids when available", () => {
    const layout = defaultLayoutForMetrics([
      "org.custom",
      "propel.cycle_time",
      "propel.merged_prs",
    ]);
    expect(layout.tiles.map((t) => t.i)).toEqual([
      "propel.cycle_time",
      "propel.merged_prs",
    ]);
  });

  it("falls back to the first available metrics", () => {
    const layout = defaultLayoutForMetrics(["org.a", "org.b", "org.c"]);
    expect(layout.tiles.map((t) => t.i)).toEqual(["org.a", "org.b", "org.c"]);
  });
});

describe("granularity helpers", () => {
  it("maps catalog grains onto filter granularities", () => {
    expect(granularitiesForMetric(["day", "week"])).toEqual(["daily", "weekly"]);
  });

  it("intersects granularities across visible metrics", () => {
    expect(
      intersectGranularities([
        { grains: ["day", "week", "month"] },
        { grains: ["week", "month"] },
      ]),
    ).toEqual(["weekly", "monthly"]);
  });
});
