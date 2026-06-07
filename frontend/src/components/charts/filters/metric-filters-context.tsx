import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { resolveDateRange } from "./time";
import {
  clampGranularity,
  DEFAULT_GRANULARITY,
  DEFAULT_RANGE,
  granularitiesForRange,
  type Granularity,
  type MetricFilters,
  type RelativeRange,
  type ResolvedDateRange,
} from "./types";

export interface MetricFiltersContextValue {
  filters: MetricFilters;
  /** Concrete start/end dates derived from the selected range. */
  dateRange: ResolvedDateRange;
  /** Granularities valid for the current range. */
  availableGranularities: Granularity[];
  setRange: (range: RelativeRange) => void;
  setGranularity: (granularity: Granularity) => void;
}

const MetricFiltersContext = createContext<MetricFiltersContextValue | null>(
  null,
);

export interface MetricFiltersProviderProps {
  children: ReactNode;
  initialRange?: RelativeRange;
  initialGranularity?: Granularity;
}

/**
 * Shares one date range + granularity selection across every chart beneath it.
 * Drop charts anywhere inside the provider and wire them to {@link useMetricFilters}
 * (directly or via {@link useResampledSeries}) so a single picker controls them all.
 */
export function MetricFiltersProvider({
  children,
  initialRange = DEFAULT_RANGE,
  initialGranularity,
}: MetricFiltersProviderProps) {
  const [range, setRangeState] = useState<RelativeRange>(initialRange);
  const [granularity, setGranularityState] = useState<Granularity>(
    clampGranularity(
      initialRange,
      initialGranularity ?? DEFAULT_GRANULARITY[initialRange],
    ),
  );

  const setRange = useCallback((next: RelativeRange) => {
    setRangeState(next);
    // Keep granularity valid for the new range.
    setGranularityState((current) => clampGranularity(next, current));
  }, []);

  const setGranularity = useCallback(
    (next: Granularity) => {
      setGranularityState(clampGranularity(range, next));
    },
    [range],
  );

  const value = useMemo<MetricFiltersContextValue>(
    () => ({
      filters: { range, granularity },
      dateRange: resolveDateRange(range),
      availableGranularities: granularitiesForRange(range),
      setRange,
      setGranularity,
    }),
    [range, granularity, setRange, setGranularity],
  );

  return (
    <MetricFiltersContext.Provider value={value}>
      {children}
    </MetricFiltersContext.Provider>
  );
}

/** Reads the shared metric filters. Must be used within a MetricFiltersProvider. */
export function useMetricFilters(): MetricFiltersContextValue {
  const context = useContext(MetricFiltersContext);
  if (!context) {
    throw new Error(
      "useMetricFilters must be used within a <MetricFiltersProvider />",
    );
  }
  return context;
}
