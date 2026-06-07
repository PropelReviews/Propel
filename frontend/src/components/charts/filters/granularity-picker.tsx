import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

import { GRANULARITIES, type Granularity } from "./types";

export interface GranularityPickerProps {
  value: Granularity;
  onValueChange: (value: Granularity) => void;
  /** Restricts selectable granularities (e.g. those valid for the range). */
  options?: Granularity[];
  className?: string;
}

/**
 * Controlled data-granularity selector (Daily / Weekly / Monthly). Pass
 * `options` to limit choices to those valid for the current range.
 */
export function GranularityPicker({
  value,
  onValueChange,
  options,
  className,
}: GranularityPickerProps) {
  const items = options
    ? GRANULARITIES.filter((g) => options.includes(g.value))
    : GRANULARITIES;

  return (
    <Select value={value} onValueChange={(next) => onValueChange(next as Granularity)}>
      <SelectTrigger className={cn("w-[130px]", className)} aria-label="Granularity">
        <SelectValue placeholder="Granularity" />
      </SelectTrigger>
      <SelectContent>
        {items.map((granularity) => (
          <SelectItem key={granularity.value} value={granularity.value}>
            {granularity.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
