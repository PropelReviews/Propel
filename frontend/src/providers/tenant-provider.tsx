import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { PermissionKey, Role } from "@/lib/permissions";
import { listTenants, type Tenant } from "@/lib/tenants";
import { useAuth } from "@/providers/auth-provider";

const TENANT_STORAGE_KEY = "propel_tenant_id";

type TenantStatus = "idle" | "loading" | "ready" | "error";

type TenantContextValue = {
  /** All tenants the user belongs to. */
  tenants: Tenant[];
  /** The selected tenant (null while loading or when the user has none). */
  tenant: Tenant | null;
  role: Role | null;
  permissions: PermissionKey[];
  status: TenantStatus;
  setTenant: (tenantId: string) => void;
  refresh: () => Promise<void>;
};

const TenantContext = createContext<TenantContextValue | null>(null);

/** The result of the last tenant fetch, tagged with the token that made it. */
type LoadResult = {
  token: string;
  tenants: Tenant[];
  error: boolean;
};

function readStoredTenantId(): string | null {
  try {
    return localStorage.getItem(TENANT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredTenantId(tenantId: string | null) {
  try {
    if (tenantId) localStorage.setItem(TENANT_STORAGE_KEY, tenantId);
    else localStorage.removeItem(TENANT_STORAGE_KEY);
  } catch {
    // Ignore storage failures (private mode, disabled storage).
  }
}

export function TenantProvider({ children }: { children: ReactNode }) {
  const { status: authStatus } = useAuth();
  const [loaded, setLoaded] = useState<LoadResult | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    readStoredTenantId(),
  );

  useEffect(() => {
    if (authStatus !== "authenticated") return;

    let cancelled = false;
    (async () => {
      try {
        const tenants = await listTenants();
        if (!cancelled) setLoaded({ token: "session", tenants, error: false });
      } catch {
        if (!cancelled) setLoaded({ token: "session", tenants: [], error: true });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authStatus]);

  const refresh = useCallback(async () => {
    if (authStatus !== "authenticated") return;
    try {
      const tenants = await listTenants();
      setLoaded({ token: "session", tenants, error: false });
    } catch {
      setLoaded({ token: "session", tenants: [], error: true });
    }
  }, [authStatus]);

  // Derive everything from the load result so signing out (or switching
  // users) never shows another session's tenants.
  const current =
    authStatus === "authenticated" && loaded?.token === "session" ? loaded : null;
  const tenants = useMemo(() => current?.tenants ?? [], [current]);
  const status: TenantStatus =
    authStatus === "anonymous"
      ? "idle"
      : !current
        ? "loading"
        : current.error
          ? "error"
          : "ready";

  // Resolve the selection: stored choice if still valid, else first tenant.
  const tenant = useMemo(() => {
    if (tenants.length === 0) return null;
    return tenants.find((t) => t.id === selectedId) ?? tenants[0];
  }, [tenants, selectedId]);

  const setTenant = useCallback((tenantId: string) => {
    setSelectedId(tenantId);
    writeStoredTenantId(tenantId);
  }, []);

  const value = useMemo<TenantContextValue>(
    () => ({
      tenants,
      tenant,
      role: tenant?.role ?? null,
      permissions: tenant?.permissions ?? [],
      status,
      setTenant,
      refresh,
    }),
    [tenants, tenant, status, setTenant, refresh],
  );

  return <TenantContext value={value}>{children}</TenantContext>;
}

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return ctx;
}
