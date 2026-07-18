import { useCallback, useEffect, useRef, useState } from "react";

import type { Granularity, RelativeRange } from "@/components/charts";
import {
  getDashboardPreference,
  putDashboardPreference,
} from "@/lib/dashboard-preference";
import {
  defaultLayoutForMetrics,
  loadLocalLayout,
  myMetricsStorageKey,
  saveLocalLayout,
  tilesFromMetricIds,
  type DashboardLayoutV2,
  type DashboardTile,
} from "./dashboard-layout";

export type BackupStatus = "idle" | "saving" | "saved" | "error";

const BACKUP_DEBOUNCE_MS = 800;

/**
 * Local-first dashboard layout with debounced server backup.
 *
 * Parent should remount (via key) when userId/tenantId change so localStorage
 * is re-read through the initial state initializer.
 */
export function useMyMetricsLayout(
  userId: string,
  tenantId: string,
  token: string | null,
  availableMetricIds: readonly string[] | null,
) {
  const storageKey = myMetricsStorageKey(userId, tenantId);
  const [layout, setLayout] = useState<DashboardLayoutV2 | null>(() =>
    loadLocalLayout(storageKey),
  );
  const [hydrated, setHydrated] = useState(() => loadLocalLayout(storageKey) !== null);
  const [backupStatus, setBackupStatus] = useState<BackupStatus>("idle");
  const backupTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const layoutRef = useRef<DashboardLayoutV2 | null>(layout);

  useEffect(() => {
    layoutRef.current = layout;
  }, [layout]);

  // Restore from server only when local storage had nothing.
  useEffect(() => {
    if (hydrated) return;

    let cancelled = false;
    void (async () => {
      if (token) {
        try {
          const remote = await getDashboardPreference(token, tenantId);
          if (cancelled) return;
          if (remote?.layout) {
            saveLocalLayout(storageKey, remote.layout);
            layoutRef.current = remote.layout;
            setLayout(remote.layout);
            setHydrated(true);
            return;
          }
        } catch {
          // Fall through to catalog defaults.
        }
      }

      if (cancelled) return;
      if (availableMetricIds) {
        const defaults = defaultLayoutForMetrics(availableMetricIds);
        saveLocalLayout(storageKey, defaults);
        layoutRef.current = defaults;
        setLayout(defaults);
      }
      setHydrated(true);
    })();

    return () => {
      cancelled = true;
    };
  }, [availableMetricIds, hydrated, storageKey, tenantId, token]);

  const persist = useCallback(
    (next: DashboardLayoutV2) => {
      layoutRef.current = next;
      setLayout(next);
      saveLocalLayout(storageKey, next);

      if (!token) return;
      if (backupTimer.current) clearTimeout(backupTimer.current);
      setBackupStatus("saving");
      backupTimer.current = setTimeout(() => {
        void (async () => {
          try {
            await putDashboardPreference(token, tenantId, next);
            setBackupStatus("saved");
          } catch {
            setBackupStatus("error");
          }
        })();
      }, BACKUP_DEBOUNCE_MS);
    },
    [storageKey, tenantId, token],
  );

  useEffect(() => {
    return () => {
      if (backupTimer.current) clearTimeout(backupTimer.current);
    };
  }, []);

  const retryBackup = useCallback(() => {
    const current = layoutRef.current;
    if (!current || !token) return;
    setBackupStatus("saving");
    void (async () => {
      try {
        await putDashboardPreference(token, tenantId, current);
        setBackupStatus("saved");
      } catch {
        setBackupStatus("error");
      }
    })();
  }, [tenantId, token]);

  const setTiles = useCallback(
    (tiles: DashboardTile[]) => {
      const current = layoutRef.current;
      if (!current) return;
      persist({ ...current, tiles });
    },
    [persist],
  );

  const setFilters = useCallback(
    (range: RelativeRange, granularity: Granularity) => {
      const current = layoutRef.current;
      if (!current) return;
      persist({ ...current, range, granularity });
    },
    [persist],
  );

  const addWidget = useCallback(
    (metricId: string) => {
      const current = layoutRef.current;
      if (!current) return;
      if (current.tiles.some((tile) => tile.i === metricId)) return;
      const maxY = current.tiles.reduce(
        (acc, tile) => Math.max(acc, tile.y + tile.h),
        0,
      );
      const [tile] = tilesFromMetricIds([metricId]);
      persist({
        ...current,
        tiles: [...current.tiles, { ...tile, y: maxY }],
      });
    },
    [persist],
  );

  const removeWidget = useCallback(
    (metricId: string) => {
      const current = layoutRef.current;
      if (!current) return;
      persist({
        ...current,
        tiles: current.tiles.filter((tile) => tile.i !== metricId),
      });
    },
    [persist],
  );

  const resetWidgets = useCallback(() => {
    if (!availableMetricIds) return;
    persist(defaultLayoutForMetrics(availableMetricIds));
  }, [availableMetricIds, persist]);

  return {
    layout,
    hydrated,
    backupStatus,
    retryBackup,
    setTiles,
    setFilters,
    addWidget,
    removeWidget,
    resetWidgets,
  };
}
