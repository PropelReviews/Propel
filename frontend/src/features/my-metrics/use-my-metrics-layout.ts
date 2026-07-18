import { useCallback, useState } from "react";

import {
  DEFAULT_WIDGET_IDS,
  isWidgetId,
  type MyMetricsWidgetId,
} from "./widget-catalog";

// Layout is a per-user, per-workspace ordered widget list in localStorage —
// CloudWatch-style personalization without an API round trip. An empty array
// is a valid saved state ("I removed everything"), distinct from no key at
// all (first visit → defaults).

export function myMetricsStorageKey(userId: string, tenantId: string): string {
  return `propel_my_metrics:${userId}:${tenantId}`;
}

export function loadLayout(storageKey: string): MyMetricsWidgetId[] {
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw === null) return [...DEFAULT_WIDGET_IDS];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [...DEFAULT_WIDGET_IDS];
    // Drop ids from removed/renamed widgets and any duplicates.
    return [...new Set(parsed.filter(isWidgetId))];
  } catch {
    return [...DEFAULT_WIDGET_IDS];
  }
}

function saveLayout(storageKey: string, widgets: MyMetricsWidgetId[]): void {
  try {
    localStorage.setItem(storageKey, JSON.stringify(widgets));
  } catch {
    // Storage full/unavailable — the in-memory layout still works this session.
  }
}

export function useMyMetricsLayout(userId: string, tenantId: string) {
  const storageKey = myMetricsStorageKey(userId, tenantId);
  const [widgets, setWidgets] = useState<MyMetricsWidgetId[]>(() =>
    loadLayout(storageKey),
  );

  const addWidget = useCallback(
    (id: MyMetricsWidgetId) => {
      setWidgets((current) => {
        if (current.includes(id)) return current;
        const next = [...current, id];
        saveLayout(storageKey, next);
        return next;
      });
    },
    [storageKey],
  );

  const removeWidget = useCallback(
    (id: MyMetricsWidgetId) => {
      setWidgets((current) => {
        const next = current.filter((widget) => widget !== id);
        saveLayout(storageKey, next);
        return next;
      });
    },
    [storageKey],
  );

  const resetWidgets = useCallback(() => {
    const next = [...DEFAULT_WIDGET_IDS];
    saveLayout(storageKey, next);
    setWidgets(next);
  }, [storageKey]);

  return { widgets, addWidget, removeWidget, resetWidgets };
}
