import type {
  Granularity,
  RelativeRange,
  ResolvedDateRange,
} from "./types";
import { rangeDef } from "./types";

/** How to combine the daily values within a bucket. */
export type Aggregation = "sum" | "avg" | "max" | "last";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Formats a date as a `YYYY-MM-DD` string in UTC. */
export function toIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** Midnight UTC for the given date. */
export function startOfDay(date: Date): Date {
  return new Date(
    Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()),
  );
}

/** Monday (UTC) of the week containing the date. */
export function startOfWeek(date: Date): Date {
  const day = startOfDay(date);
  const weekday = (day.getUTCDay() + 6) % 7; // 0 = Monday
  return new Date(day.getTime() - weekday * DAY_MS);
}

/** First day (UTC) of the month containing the date. */
export function startOfMonth(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
}

/**
 * Resolves a relative range into concrete start/end dates. `end` is now;
 * `start` is `days` before now.
 */
export function resolveDateRange(
  range: RelativeRange,
  now: Date = new Date(),
): ResolvedDateRange {
  const end = now;
  const start = new Date(now.getTime() - rangeDef(range).days * DAY_MS);
  return { start, end };
}

/** Returns the bucket key (ISO date of the bucket start) for a granularity. */
export function bucketKey(iso: string, granularity: Granularity): string {
  const date = new Date(iso);
  if (granularity === "daily") return toIsoDate(startOfDay(date));
  if (granularity === "weekly") return toIsoDate(startOfWeek(date));
  return toIsoDate(startOfMonth(date));
}

function aggregate(values: number[], how: Aggregation): number {
  if (values.length === 0) return 0;
  switch (how) {
    case "sum":
      return values.reduce((a, b) => a + b, 0);
    case "avg":
      return values.reduce((a, b) => a + b, 0) / values.length;
    case "max":
      return Math.max(...values);
    case "last":
      return values[values.length - 1];
  }
}

export interface DailyPoint {
  date: string;
  value: number;
}

/**
 * Filters daily points to a date range, then groups them into buckets of the
 * given granularity, combining each bucket's values with `how`. Returns points
 * keyed by the bucket-start ISO date, sorted ascending.
 */
export function resample(
  points: DailyPoint[],
  {
    range,
    granularity,
    how = "sum",
    now = new Date(),
  }: {
    range: RelativeRange;
    granularity: Granularity;
    how?: Aggregation;
    now?: Date;
  },
): DailyPoint[] {
  const { start, end } = resolveDateRange(range, now);
  // Floor the start to midnight so whole-day boundaries are inclusive and the
  // first day in the window isn't dropped by the range's time-of-day component.
  const startMs = startOfDay(start).getTime();
  const endMs = end.getTime();

  const buckets = new Map<string, number[]>();
  for (const point of points) {
    const t = new Date(point.date).getTime();
    if (Number.isNaN(t) || t < startMs || t > endMs) continue;
    const key = bucketKey(point.date, granularity);
    const existing = buckets.get(key);
    if (existing) existing.push(point.value);
    else buckets.set(key, [point.value]);
  }

  return [...buckets.entries()]
    .map(([date, values]) => ({ date, value: aggregate(values, how) }))
    .sort((a, b) => a.date.localeCompare(b.date));
}
