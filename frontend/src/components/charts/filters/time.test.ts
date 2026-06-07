import { describe, expect, it } from "vitest";

import { resample, resolveDateRange, startOfWeek, toIsoDate } from "./time";
import { clampGranularity } from "./types";

const NOW = new Date("2026-06-08T12:00:00Z"); // a Monday

function dailyOnes(dates: string[]): { date: string; value: number }[] {
  return dates.map((date) => ({ date, value: 1 }));
}

describe("resolveDateRange", () => {
  it("sets start to `days` before end", () => {
    const { start, end } = resolveDateRange("week", NOW);
    expect(toIsoDate(end)).toBe("2026-06-08");
    expect(toIsoDate(start)).toBe("2026-06-01");
  });
});

describe("startOfWeek", () => {
  it("returns the Monday of the week", () => {
    expect(toIsoDate(startOfWeek(new Date("2026-06-10T00:00:00Z")))).toBe("2026-06-08");
  });
});

describe("resample", () => {
  const points = dailyOnes([
    "2026-06-01",
    "2026-06-02",
    "2026-06-03",
    "2026-06-04",
    "2026-06-05",
    "2026-06-06",
    "2026-06-07",
    "2026-06-08",
  ]);

  it("keeps one point per day at daily granularity within range", () => {
    const out = resample(points, {
      range: "week",
      granularity: "daily",
      how: "sum",
      now: NOW,
    });
    expect(out).toHaveLength(8);
    expect(out.every((p) => p.value === 1)).toBe(true);
  });

  it("buckets into weeks and sums at weekly granularity", () => {
    const out = resample(points, {
      range: "week",
      granularity: "weekly",
      how: "sum",
      now: NOW,
    });
    // Week of 06-01 (Mon) holds 06-01..06-07 = 7; week of 06-08 holds 06-08 = 1.
    expect(out).toEqual([
      { date: "2026-06-01", value: 7 },
      { date: "2026-06-08", value: 1 },
    ]);
  });

  it("averages when how is avg", () => {
    const out = resample(
      [
        { date: "2026-06-01", value: 2 },
        { date: "2026-06-02", value: 4 },
      ],
      { range: "week", granularity: "weekly", how: "avg", now: NOW },
    );
    expect(out).toEqual([{ date: "2026-06-01", value: 3 }]);
  });

  it("excludes points outside the range", () => {
    const out = resample(
      [
        { date: "2025-01-01", value: 99 },
        { date: "2026-06-08", value: 1 },
      ],
      { range: "week", granularity: "daily", how: "sum", now: NOW },
    );
    expect(out).toEqual([{ date: "2026-06-08", value: 1 }]);
  });
});

describe("clampGranularity", () => {
  it("keeps a valid granularity", () => {
    expect(clampGranularity("quarter", "weekly")).toBe("weekly");
  });

  it("falls back to the range default when invalid", () => {
    // monthly is not valid for a single day -> default daily
    expect(clampGranularity("day", "monthly")).toBe("daily");
    // daily is not valid for half_year -> default monthly
    expect(clampGranularity("half_year", "daily")).toBe("monthly");
  });
});
