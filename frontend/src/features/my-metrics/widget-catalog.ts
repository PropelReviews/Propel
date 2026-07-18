// Catalog of charts an individual can place on their My metrics dashboard.
// All widgets are person-scoped (metrics API `scope=me`). Deployment frequency
// is deliberately absent: releases are org-level and not IC-attributable.

export type MyMetricsWidgetId =
  | "pr-activity"
  | "cycle-time"
  | "review-latency"
  | "change-failure";

export type MyMetricsWidget = {
  id: MyMetricsWidgetId;
  title: string;
  description: string;
};

export const WIDGET_CATALOG: readonly MyMetricsWidget[] = [
  {
    id: "pr-activity",
    title: "Pull request activity",
    description: "PRs you opened, merged, and closed without merging.",
  },
  {
    id: "cycle-time",
    title: "Cycle time",
    description: "Hours from opening your PRs to merge (DORA lead-time proxy).",
  },
  {
    id: "review-latency",
    title: "Time to first review",
    description: "How long your PRs wait for their first review.",
  },
  {
    id: "change-failure",
    title: "Change failure rate",
    description: "Share of your merges that look like reverts (DORA CFR proxy).",
  },
] as const;

/** Every catalog widget is on by default; removing one is a personal choice. */
export const DEFAULT_WIDGET_IDS: readonly MyMetricsWidgetId[] = WIDGET_CATALOG.map(
  (widget) => widget.id,
);

const WIDGET_ID_SET = new Set<string>(DEFAULT_WIDGET_IDS);

export function isWidgetId(value: unknown): value is MyMetricsWidgetId {
  return typeof value === "string" && WIDGET_ID_SET.has(value);
}

export function getWidget(id: MyMetricsWidgetId): MyMetricsWidget {
  const widget = WIDGET_CATALOG.find((entry) => entry.id === id);
  if (!widget) throw new Error(`Unknown My metrics widget: ${id}`);
  return widget;
}
