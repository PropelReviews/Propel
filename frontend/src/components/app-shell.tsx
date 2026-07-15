import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAnyPermission } from "@/hooks/use-permission";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

function TopNavLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        cn(
          "text-muted-foreground hover:text-foreground text-sm transition-colors",
          isActive && "text-foreground font-medium",
        )
      }
    >
      {children}
    </NavLink>
  );
}

/**
 * Lightweight header shared by authenticated app pages: brand, nav (with the
 * Access link gated by management permissions), and a workspace switcher when
 * the user belongs to more than one tenant.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { status, signOut } = useAuth();
  const { tenants, tenant, setTenant } = useTenant();
  const showAccess = useAnyPermission(
    "roles:manage",
    "members:assign_role",
    "invites:read",
  );
  const showWorkspace = useAnyPermission("connections:manage");
  const showMetrics = useAnyPermission("metrics:read");
  const showMetricAdmin = useAnyPermission("metrics:manage");

  return (
    <div className="bg-background min-h-svh">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-6">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <img src="/favicon.svg" alt="" className="size-6" />
              <span className="text-gradient-brand font-semibold tracking-tight">
                Propel
              </span>
            </Link>
            {status === "authenticated" && (
              <nav className="flex items-center gap-4">
                <TopNavLink to="/home">Home</TopNavLink>
                <TopNavLink to="/data">Data</TopNavLink>
                {showMetrics && <TopNavLink to="/metrics">Metrics</TopNavLink>}
                {showWorkspace && (
                  <TopNavLink to="/settings/workspace">Workspace</TopNavLink>
                )}
                {showMetricAdmin && (
                  <TopNavLink to="/settings/metric-set">Metric set</TopNavLink>
                )}
                {showMetrics && (
                  <TopNavLink to="/settings/metric-health">Health</TopNavLink>
                )}
                {showAccess && <TopNavLink to="/settings/access">Access</TopNavLink>}
                <TopNavLink to="/profile">Profile</TopNavLink>
              </nav>
            )}
          </div>
          {status === "authenticated" && (
            <div className="flex items-center gap-3">
              {tenants.length > 1 && tenant && (
                <Select value={tenant.id} onValueChange={setTenant}>
                  <SelectTrigger
                    size="sm"
                    className="w-44"
                    aria-label="Switch workspace"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button
                variant="ghost"
                size="sm"
                analyticsName="sign_out"
                onClick={signOut}
              >
                Sign out
              </Button>
            </div>
          )}
        </div>
      </header>
      {children}
    </div>
  );
}
