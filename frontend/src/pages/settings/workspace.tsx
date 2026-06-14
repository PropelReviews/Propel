import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ApiError,
  getLinearAuthorizeUrl,
  getLinearConnection,
  type LinearConnection,
} from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

export function WorkspacePage() {
  const { token } = useAuth();
  const { tenant } = useTenant();

  return (
    <main className="bg-background mx-auto min-h-svh max-w-2xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Workspace</h1>
        <p className="text-muted-foreground mt-2">
          Manage integrations and settings for{" "}
          <span className="font-medium">{tenant?.name ?? "your workspace"}</span>.
        </p>
      </header>

      <section className="space-y-6">
        <h2 className="text-lg font-medium">Integrations</h2>
        <LinearIntegrationCard token={token} tenantId={tenant?.id ?? null} />
      </section>
    </main>
  );
}

function LinearIntegrationCard({
  token,
  tenantId,
}: {
  token: string | null;
  tenantId: string | null;
}) {
  const [params, setParams] = useSearchParams();
  const [linear, setLinear] = useState<LinearConnection | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<"connected" | "error" | null>(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    let cancelled = false;
    void (async () => {
      try {
        const result = await getLinearConnection(tenantId);
        if (!cancelled) setLinear(result);
      } catch {
        if (!cancelled) setLinear(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId]);

  // Handle the redirect back from Linear (`?linear=connected` / `?linear=error`).
  useEffect(() => {
    const result = params.get("linear");
    if (result !== "connected" && result !== "error") return;
    void (async () => {
      if (result === "connected" && token && tenantId) {
        try {
          setLinear(await getLinearConnection(tenantId));
        } catch {
          // Status refresh is best-effort; the notice still informs the user.
        }
      }
      setNotice(result);
    })();
    const next = new URLSearchParams(params);
    next.delete("linear");
    setParams(next, { replace: true });
  }, [params, setParams, token, tenantId]);

  const onConnect = async () => {
    if (!token || !tenantId) return;
    setError(null);
    setConnecting(true);
    try {
      const url = await getLinearAuthorizeUrl(tenantId);
      window.location.href = url;
    } catch (err) {
      setConnecting(false);
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "Linear isn't configured for this deployment yet."
            : err.message
          : "Could not start the Linear connection. Please try again.",
      );
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Linear</CardTitle>
        <CardDescription>
          Connect your team&apos;s Linear workspace so Propel can ingest issues for
          project velocity.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {linear?.connected ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Badge variant="secondary">Connected</Badge>
              {linear.workspace_name && (
                <span className="text-sm font-medium">{linear.workspace_name}</span>
              )}
            </div>
            <Button
              variant="outline"
              onClick={onConnect}
              disabled={connecting}
              analyticsName="linear_reconnect"
            >
              {connecting ? "Redirecting…" : "Reconnect"}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-muted-foreground text-sm">Not connected yet.</p>
            <Button
              onClick={onConnect}
              disabled={connecting}
              analyticsName="linear_connect"
              className="self-start"
            >
              {connecting ? "Redirecting…" : "Connect Linear"}
            </Button>
          </div>
        )}
        {notice === "connected" && (
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            Linear connected. Issues will sync on the next ingestion run.
          </p>
        )}
        {notice === "error" && (
          <p className="text-destructive text-sm">
            We couldn&apos;t complete the Linear connection. Please try again.
          </p>
        )}
        {error && <p className="text-destructive text-sm">{error}</p>}
      </CardContent>
    </Card>
  );
}
