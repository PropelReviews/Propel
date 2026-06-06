import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearCachedDistinctId,
  readCachedDistinctId,
  readCachedFeatureFlags,
  writeCachedDistinctId,
  writeCachedFeatureFlags,
} from "./posthog-persistence";

function createStorage() {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => {
      store.clear();
    },
  };
}

describe("posthog-persistence", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", createStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("round-trips feature flags", () => {
    writeCachedFeatureFlags({ "signup-signin": true });
    expect(readCachedFeatureFlags()).toEqual({ "signup-signin": true });
  });

  it("returns empty flags when cache is missing or corrupt", () => {
    expect(readCachedFeatureFlags()).toEqual({});
    localStorage.setItem("propel_ph_feature_flags", "not-json");
    expect(readCachedFeatureFlags()).toEqual({});
  });

  it("round-trips distinct id and identified state", () => {
    writeCachedDistinctId("user-123");
    expect(readCachedDistinctId()).toEqual({
      distinctId: "user-123",
      isIdentified: true,
    });
  });

  it("clears distinct id cache", () => {
    writeCachedDistinctId("user-123");
    clearCachedDistinctId();
    expect(readCachedDistinctId()).toEqual({
      distinctId: null,
      isIdentified: false,
    });
  });
});
