/** Formats a count with compact notation (e.g. `1.2k`). */
export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

/**
 * Formats a duration given in hours into the largest sensible unit
 * (minutes, hours, or days).
 */
export function formatDuration(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Number(hours.toFixed(1))}h`;
  return `${Number((hours / 24).toFixed(1))}d`;
}

/** Formats a 0–100 number as a whole-number percentage. */
export function formatPercent(value: number): string {
  return `${Math.round(value)}%`;
}

/** Formats an ISO date as a short month/day label (e.g. `Jan 5`). */
export function formatWeekLabel(isoDate: string): string {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return isoDate;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}
