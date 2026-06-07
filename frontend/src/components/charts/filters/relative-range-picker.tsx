import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

import { RELATIVE_RANGES, type RelativeRange } from "./types";

export interface RelativeRangePickerProps {
  value: RelativeRange;
  onValueChange: (value: RelativeRange) => void;
  className?: string;
}

/**
 * Controlled relative-range selector (Last 24 hours … Last year). Presentational
 * only — wire it to shared state via {@link MetricFiltersBar} or your own handler.
 */
export function RelativeRangePicker({
  value,
  onValueChange,
  className,
}: RelativeRangePickerProps) {
  return (
    <Select
      value={value}
      onValueChange={(next) => onValueChange(next as RelativeRange)}
    >
      <SelectTrigger
        className={cn("w-[160px]", className)}
        aria-label="Date range"
      >
        <SelectValue placeholder="Date range" />
      </SelectTrigger>
      <SelectContent>
        {RELATIVE_RANGES.map((range) => (
          <SelectItem key={range.value} value={range.value}>
            {range.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
