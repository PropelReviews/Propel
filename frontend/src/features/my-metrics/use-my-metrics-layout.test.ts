import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadLayout, myMetricsStorageKey } from "./use-my-metrics-layout";
import { DEFAULT_WIDGET_IDS } from "./widget-catalog";

const KEY = myMetricsStorageKey("user-1", "tenant-1");

// Node has no localStorage; back the global with a simple in-memory store.
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
    expect(myMetricsStorageKey("user-1", "tenant-2")).not.toBe(KEY);
  });
});

describe("loadLayout", () => {
  it("returns the default widgets when nothing is stored", () => {
    expect(loadLayout(KEY)).toEqual([...DEFAULT_WIDGET_IDS]);
  });

  it("returns a stored layout, preserving order", () => {
    store.set(KEY, JSON.stringify(["change-failure", "pr-activity"]));
    expect(loadLayout(KEY)).toEqual(["change-failure", "pr-activity"]);
  });

  it("treats a stored empty array as 'all charts removed', not defaults", () => {
    store.set(KEY, JSON.stringify([]));
    expect(loadLayout(KEY)).toEqual([]);
  });

  it("drops unknown widget ids and duplicates", () => {
    store.set(
      KEY,
      JSON.stringify(["cycle-time", "retired-widget", "cycle-time", 42, null]),
    );
    expect(loadLayout(KEY)).toEqual(["cycle-time"]);
  });

  it("falls back to defaults on malformed JSON", () => {
    store.set(KEY, "{not json");
    expect(loadLayout(KEY)).toEqual([...DEFAULT_WIDGET_IDS]);
  });

  it("falls back to defaults when the stored value is not an array", () => {
    store.set(KEY, JSON.stringify({ widgets: ["cycle-time"] }));
    expect(loadLayout(KEY)).toEqual([...DEFAULT_WIDGET_IDS]);
  });
});
