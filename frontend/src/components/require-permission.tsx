import type { ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { PermissionKey } from "@/lib/permissions";
import { useTenant } from "@/providers/tenant-provider";

/**
 * Renders children only when the current user holds at least one of the
 * listed permissions in the selected tenant; otherwise shows a 403 card.
 */
export function RequirePermission({
  anyOf,
  children,
}: {
  anyOf: PermissionKey[];
  children: ReactNode;
}) {
  const { permissions, status, tenant } = useTenant();

  if (status === "loading" || status === "idle") {
    return (
      <main className="flex min-h-svh items-center justify-center p-8">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    );
  }

  if (!tenant || !anyOf.some((key) => permissions.includes(key))) {
    return (
      <main className="flex min-h-svh items-center justify-center p-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Access denied</CardTitle>
            <CardDescription>
              {tenant
                ? "You don't have permission to view this page. Ask a workspace admin for access."
                : "You don't belong to a workspace yet."}
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      </main>
    );
  }

  return children;
}
