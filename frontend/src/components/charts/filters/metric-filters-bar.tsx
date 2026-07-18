import { cn } from "@/lib/utils";

import { GranularityPicker } from "./granularity-picker";
import { useMetricFilters } from "./metric-filters-context";
import { RelativeRangePicker } from "./relative-range-picker";
import type { Granularity } from "./types";

export interface MetricFiltersBarProps {
  className?: string;
  /** Hide the granularity picker when only a range is relevant. */
  hideGranularity?: boolean;
  /**
   * Optional override for selectable granularities (e.g. intersection of
   * metrics on a dashboard). Falls back to range-valid options from context.
   */
  granularityOptions?: Granularity[];
}

/**
 * The control that links a date picker to every chart on the page. Renders the
 * relative-range and granularity pickers wired to the shared
 * {@link MetricFiltersProvider}; any linked chart beneath the provider updates
 * when these change.
 */
export function MetricFiltersBar({
  className,
  hideGranularity = false,
  granularityOptions,
}: MetricFiltersBarProps) {
  const { filters, availableGranularities, setRange, setGranularity } =
    useMetricFilters();
  const options = granularityOptions ?? availableGranularities;

  return (
    <div
      data-slot="metric-filters-bar"
      className={cn("flex flex-wrap items-center gap-2", className)}
    >
      <RelativeRangePicker value={filters.range} onValueChange={setRange} />
      {hideGranularity ? null : (
        <GranularityPicker
          value={filters.granularity}
          onValueChange={setGranularity}
          options={options}
        />
      )}
    </div>
  );
}
