import { cn } from "@/lib/utils";

import { GranularityPicker } from "./granularity-picker";
import { useMetricFilters } from "./metric-filters-context";
import { RelativeRangePicker } from "./relative-range-picker";

export interface MetricFiltersBarProps {
  className?: string;
  /** Hide the granularity picker when only a range is relevant. */
  hideGranularity?: boolean;
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
}: MetricFiltersBarProps) {
  const {
    filters,
    availableGranularities,
    setRange,
    setGranularity,
  } = useMetricFilters();

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
          options={availableGranularities}
        />
      )}
    </div>
  );
}
