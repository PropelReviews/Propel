/** A relative look-back window for metrics. */
export type RelativeRange = "day" | "week" | "month" | "quarter" | "half_year" | "year";

/** The bucket size used to aggregate data points within a range. */
export type Granularity = "daily" | "weekly" | "monthly";

export interface RangeDef {
  value: RelativeRange;
  label: string;
  /** Look-back length in days. */
  days: number;
}

export interface GranularityDef {
  value: Granularity;
  label: string;
}

/** Selectable relative ranges, in display order. */
export const RELATIVE_RANGES: RangeDef[] = [
  { value: "day", label: "Last 24 hours", days: 1 },
  { value: "week", label: "Last 7 days", days: 7 },
  { value: "month", label: "Last 30 days", days: 30 },
  { value: "quarter", label: "Last quarter", days: 90 },
  { value: "half_year", label: "Last 6 months", days: 182 },
  { value: "year", label: "Last year", days: 365 },
];

/** All granularities, in display order. */
export const GRANULARITIES: GranularityDef[] = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
];

/**
 * Granularities that make sense for each range. Prevents nonsensical
 * combinations (e.g. monthly buckets over a single day).
 */
export const GRANULARITY_BY_RANGE: Record<RelativeRange, Granularity[]> = {
  day: ["daily"],
  week: ["daily"],
  month: ["daily", "weekly"],
  quarter: ["daily", "weekly", "monthly"],
  half_year: ["weekly", "monthly"],
  year: ["weekly", "monthly"],
};

/** Sensible default granularity for each range. */
export const DEFAULT_GRANULARITY: Record<RelativeRange, Granularity> = {
  day: "daily",
  week: "daily",
  month: "weekly",
  quarter: "weekly",
  half_year: "monthly",
  year: "monthly",
};

export interface MetricFilters {
  range: RelativeRange;
  granularity: Granularity;
}

export interface ResolvedDateRange {
  start: Date;
  end: Date;
}

export const DEFAULT_RANGE: RelativeRange = "quarter";

export function rangeDef(range: RelativeRange): RangeDef {
  return RELATIVE_RANGES.find((r) => r.value === range) ?? RELATIVE_RANGES[3];
}

/** Returns the granularities valid for a range. */
export function granularitiesForRange(range: RelativeRange): Granularity[] {
  return GRANULARITY_BY_RANGE[range];
}

/**
 * Clamps a granularity to one valid for the range, falling back to the range's
 * default when the current choice is no longer allowed.
 */
export function clampGranularity(
  range: RelativeRange,
  granularity: Granularity,
): Granularity {
  return granularitiesForRange(range).includes(granularity)
    ? granularity
    : DEFAULT_GRANULARITY[range];
}
