const FEATURE_FLAGS_KEY = "propel_ph_feature_flags";
const DISTINCT_ID_KEY = "propel_ph_distinct_id";
const IDENTIFIED_KEY = "propel_ph_identified";

export type CachedFeatureFlags = Record<string, boolean | string>;

function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Ignore storage failures (private mode, disabled storage).
  }
}

export function readCachedFeatureFlags(): CachedFeatureFlags {
  const raw = readStorage(FEATURE_FLAGS_KEY);
  if (!raw) return {};
  try {
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as CachedFeatureFlags;
    }
  } catch {
    // Ignore corrupt cache.
  }
  return {};
}

export function writeCachedFeatureFlags(flags: CachedFeatureFlags) {
  writeStorage(FEATURE_FLAGS_KEY, JSON.stringify(flags));
}

export function readCachedDistinctId(): {
  distinctId: string | null;
  isIdentified: boolean;
} {
  return {
    distinctId: readStorage(DISTINCT_ID_KEY),
    isIdentified: readStorage(IDENTIFIED_KEY) === "true",
  };
}

export function writeCachedDistinctId(distinctId: string, isIdentified = true) {
  writeStorage(DISTINCT_ID_KEY, distinctId);
  writeStorage(IDENTIFIED_KEY, isIdentified ? "true" : "false");
}

export function clearCachedDistinctId() {
  writeStorage(DISTINCT_ID_KEY, null);
  writeStorage(IDENTIFIED_KEY, null);
}
