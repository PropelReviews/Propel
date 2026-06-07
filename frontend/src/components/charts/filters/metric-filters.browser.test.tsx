import { afterEach, describe, expect, it } from "vitest";

import { mockDailyThroughput } from "@/lib/mock-metrics";
import { renderInDom, waitFor } from "@/test/render-browser";

import { GranularityPicker } from "./granularity-picker";
import { MetricFiltersProvider, useMetricFilters } from "./metric-filters-context";
import { RelativeRangePicker } from "./relative-range-picker";
import { useResampledSeries } from "./use-resampled-series";

let result: ReturnType<typeof renderInDom> | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

/** Surfaces filter state + linked-series length so the test can assert linkage. */
function Harness() {
  const { filters, availableGranularities, setRange, setGranularity } =
    useMetricFilters();
  const data = useResampledSeries(mockDailyThroughput, { how: "sum" });

  return (
    <div>
      <span data-testid="count">{data.length}</span>
      <span data-testid="range">{filters.range}</span>
      <span data-testid="gran">{filters.granularity}</span>
      <span data-testid="avail">{availableGranularities.join(",")}</span>
      <button data-testid="set-week" onClick={() => setRange("week")}>
        week
      </button>
      <button data-testid="set-year" onClick={() => setRange("year")}>
        year
      </button>
      <button data-testid="set-monthly" onClick={() => setGranularity("monthly")}>
        monthly
      </button>
    </div>
  );
}

function text(container: HTMLElement, testid: string): string {
  return (
    container.querySelector(`[data-testid="${testid}"]`)?.textContent ?? ""
  );
}

describe("MetricFilters linking", () => {
  it("links resampled series to the shared range and granularity", async () => {
    result = renderInDom(
      <MetricFiltersProvider initialRange="quarter">
        <Harness />
      </MetricFiltersProvider>,
    );
    const { container } = result;

    await waitFor(() => text(container, "count") !== "");
    expect(text(container, "range")).toBe("quarter");
    expect(text(container, "gran")).toBe("weekly");
    const quarterCount = Number(text(container, "count"));
    expect(quarterCount).toBeGreaterThan(0);

    // Narrowing to a week reduces the number of points and clamps granularity
    // to daily (weekly/monthly are invalid for a 7-day window).
    container.querySelector<HTMLButtonElement>('[data-testid="set-week"]')!.click();
    await waitFor(() => text(container, "range") === "week");
    expect(text(container, "gran")).toBe("daily");
    expect(text(container, "avail")).toBe("daily");
    expect(Number(text(container, "count"))).toBeLessThan(quarterCount);
  });

  it("clamps an invalid granularity when the range changes", async () => {
    result = renderInDom(
      <MetricFiltersProvider initialRange="month" initialGranularity="daily">
        <Harness />
      </MetricFiltersProvider>,
    );
    const { container } = result;

    await waitFor(() => text(container, "gran") === "daily");

    // Switch to a year: daily is no longer valid, so it clamps to monthly.
    container.querySelector<HTMLButtonElement>('[data-testid="set-year"]')!.click();
    await waitFor(() => text(container, "range") === "year");
    expect(text(container, "gran")).toBe("monthly");
    expect(text(container, "avail")).toBe("weekly,monthly");
  });
});

describe("filter pickers", () => {
  it("renders a range picker trigger", async () => {
    result = renderInDom(
      <RelativeRangePicker value="quarter" onValueChange={() => {}} />,
    );
    const { container } = result;

    await waitFor(
      () => container.querySelector('[aria-label="Date range"]') !== null,
    );
  });

  it("renders a granularity picker trigger", async () => {
    result = renderInDom(
      <GranularityPicker
        value="weekly"
        onValueChange={() => {}}
        options={["daily", "weekly"]}
      />,
    );
    const { container } = result;

    await waitFor(
      () => container.querySelector('[aria-label="Granularity"]') !== null,
    );
  });
});
