import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle } from "lucide-react";

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
  getGithubTenantInstallUrl,
  getLinearAuthorizeUrl,
  getLinearConnection,
  listConnections,
  syncGithubInstallations,
  type Connection,
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
        <GitHubIntegrationCard token={token} tenantId={tenant?.id ?? null} />
        <LinearIntegrationCard token={token} tenantId={tenant?.id ?? null} />
      </section>
    </main>
  );
}

type CheckState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "not-found" }
  | { status: "error"; message: string };

function isHealthy(status: string) {
  return status === "active";
}

function SyncFailureAlert({ provider }: { provider: "github" | "linear" }) {
  return (
    <div
      role="alert"
      className="border-destructive/60 bg-destructive/5 text-destructive flex gap-3 rounded-lg border p-3"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="space-y-2 text-sm">
        <p className="text-destructive font-medium">Latest sync failed</p>
        {provider === "linear" ? (
          <>
            <p>
              Reconnect Linear to refresh credentials. If Linear says the app is already
              installed, revoke it first so OAuth can issue a new token:
            </p>
            <ol className="text-destructive/90 list-decimal space-y-1 pl-5">
              <li>
                In Linear, open{" "}
                <span className="font-medium">Settings → Installed Applications</span>
              </li>
              <li>
                Find Propel → <span className="font-medium">Manage</span> →{" "}
                <span className="font-medium">Revoke Access</span>
              </li>
              <li>Return here and click Reconnect</li>
            </ol>
          </>
        ) : (
          <p>
            Reinstall the GitHub App on your organization, then click{" "}
            <span className="font-medium">I&apos;ve installed it</span> so Propel can
            pick up the installation again.
          </p>
        )}
      </div>
    </div>
  );
}

function GitHubIntegrationCard({
  token,
  tenantId,
}: {
  token: string | null;
  tenantId: string | null;
}) {
  const [accounts, setAccounts] = useState<Connection[] | null>(null);
  const [opening, setOpening] = useState(false);
  const [check, setCheck] = useState<CheckState>({ status: "idle" });
  const [error, setError] = useState<string | null>(null);

  async function refreshConnections() {
    if (!token || !tenantId) return [];
    const all = await listConnections(token, tenantId);
    const github = all.filter((c) => c.provider === "github");
    setAccounts(github);
    return github.filter((c) => isHealthy(c.status));
  }

  useEffect(() => {
    if (!token || !tenantId) return;
    let cancelled = false;
    void (async () => {
      try {
        const all = await listConnections(token, tenantId);
        if (!cancelled) {
          setAccounts(all.filter((c) => c.provider === "github"));
        }
      } catch {
        if (!cancelled) setAccounts(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId]);

  const onInstall = async () => {
    if (!token || !tenantId) return;
    setError(null);
    setCheck({ status: "idle" });
    setOpening(true);
    try {
      const url = await getGithubTenantInstallUrl(token, tenantId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "GitHub App isn't configured for this deployment yet."
            : err.message
          : "Could not open the GitHub install page. Please try again.",
      );
    } finally {
      setOpening(false);
    }
  };

  const onCheck = async () => {
    if (!token || !tenantId) return;
    setError(null);
    setCheck({ status: "checking" });
    try {
      await syncGithubInstallations(token);
      const healthy = await refreshConnections();
      setCheck(healthy.length > 0 ? { status: "idle" } : { status: "not-found" });
    } catch (err) {
      setCheck({
        status: "error",
        message:
          err instanceof ApiError
            ? err.message
            : "Could not check the GitHub connection.",
      });
    }
  };

  const healthy = accounts?.filter((c) => isHealthy(c.status)) ?? [];
  const broken =
    accounts?.filter((c) => !isHealthy(c.status) || Boolean(c.auth_error)) ?? [];
  const connected = healthy.length > 0;
  const hasAuthIssue = !connected && broken.length > 0;
  const syncErrorAccount =
    accounts?.find((c) => c.last_sync_status === "error" && c.last_sync_error) ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>GitHub</CardTitle>
        <CardDescription>
          Install the Propel GitHub App on your organization to ingest commits, pull
          requests, reviews, and Copilot usage.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {connected ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">Connected</Badge>
                {healthy.map((account) => (
                  <span key={account.id} className="text-sm font-medium">
                    {account.external_account_name ?? account.external_account_id}
                  </span>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={onInstall}
                  disabled={opening}
                  analyticsName="github_workspace_reinstall"
                >
                  {opening ? "Opening…" : "Install again"}
                </Button>
                <Button
                  variant="outline"
                  onClick={onCheck}
                  disabled={check.status === "checking"}
                  analyticsName="github_workspace_check"
                >
                  {check.status === "checking" ? "Checking…" : "I've installed it"}
                </Button>
              </div>
            </div>
            {syncErrorAccount && <SyncFailureAlert provider="github" />}
          </div>
        ) : hasAuthIssue ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="destructive">Needs reconnect</Badge>
              {broken.map((account) => (
                <span key={account.id} className="text-sm font-medium">
                  {account.external_account_name ?? account.external_account_id}
                </span>
              ))}
            </div>
            <p className="text-destructive text-sm">
              {broken.find((a) => a.auth_error)?.auth_error ??
                "Ingestion could not authenticate this GitHub App installation. Reinstall the app, then click I've installed it."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={onInstall}
                disabled={opening}
                analyticsName="github_workspace_reinstall"
              >
                {opening ? "Opening…" : "Reinstall GitHub App"}
              </Button>
              <Button
                variant="outline"
                onClick={onCheck}
                disabled={check.status === "checking"}
                analyticsName="github_workspace_check"
              >
                {check.status === "checking" ? "Checking…" : "I've installed it"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-muted-foreground text-sm">Not connected yet.</p>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={onInstall}
                disabled={opening}
                analyticsName="github_workspace_install"
              >
                {opening ? "Opening…" : "Install GitHub App"}
              </Button>
              <Button
                variant="outline"
                onClick={onCheck}
                disabled={check.status === "checking"}
                analyticsName="github_workspace_check"
              >
                {check.status === "checking" ? "Checking…" : "I've installed it"}
              </Button>
            </div>
          </div>
        )}
        {check.status === "not-found" && (
          <p className="text-muted-foreground text-sm">
            We couldn&apos;t find a GitHub App installation for this workspace yet. Make
            sure the app is installed on your organization, then check again.
          </p>
        )}
        {check.status === "error" && (
          <p className="text-destructive text-sm">{check.message}</p>
        )}
        {error && <p className="text-destructive text-sm">{error}</p>}
      </CardContent>
    </Card>
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
  const [opening, setOpening] = useState(false);
  const [check, setCheck] = useState<CheckState>({ status: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<"connected" | "error" | null>(null);

  useEffect(() => {
    if (!token || !tenantId) return;
    let cancelled = false;
    void (async () => {
      try {
        const result = await getLinearConnection(token, tenantId);
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
          setLinear(await getLinearConnection(token, tenantId));
        } catch {
          // Status refresh is best-effort; the notice still informs the user.
        }
      }
      setNotice(result);
      setCheck({ status: "idle" });
    })();
    const next = new URLSearchParams(params);
    next.delete("linear");
    setParams(next, { replace: true });
  }, [params, setParams, token, tenantId]);

  const onConnect = async () => {
    if (!token || !tenantId) return;
    setError(null);
    setCheck({ status: "idle" });
    setOpening(true);
    try {
      const url = await getLinearAuthorizeUrl(token, tenantId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "Linear isn't configured for this deployment yet."
            : err.message
          : "Could not start the Linear connection. Please try again.",
      );
    } finally {
      setOpening(false);
    }
  };

  const onCheck = async () => {
    if (!token || !tenantId) return;
    setError(null);
    setCheck({ status: "checking" });
    try {
      const result = await getLinearConnection(token, tenantId);
      setLinear(result);
      if (result.connected) {
        setCheck({ status: "idle" });
        setNotice("connected");
      } else {
        setCheck({ status: "not-found" });
      }
    } catch (err) {
      setCheck({
        status: "error",
        message:
          err instanceof ApiError
            ? err.message
            : "Could not check the Linear connection.",
      });
    }
  };

  const hasAuthIssue =
    Boolean(linear) &&
    !linear?.connected &&
    (Boolean(linear?.auth_error) ||
      linear?.status === "paused" ||
      linear?.status === "revoked");
  const hasSyncFailure =
    linear?.last_sync_status === "error" && Boolean(linear.last_sync_error);

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
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">Connected</Badge>
                {linear.workspace_name && (
                  <span className="text-sm font-medium">{linear.workspace_name}</span>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  onClick={onConnect}
                  disabled={opening}
                  analyticsName="linear_reconnect"
                >
                  {opening ? "Opening…" : "Reconnect"}
                </Button>
                <Button
                  variant="outline"
                  onClick={onCheck}
                  disabled={check.status === "checking"}
                  analyticsName="linear_check"
                >
                  {check.status === "checking" ? "Checking…" : "I've connected it"}
                </Button>
              </div>
            </div>
            {hasSyncFailure && <SyncFailureAlert provider="linear" />}
          </div>
        ) : hasAuthIssue ? (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="destructive">Needs reconnect</Badge>
              {linear?.workspace_name && (
                <span className="text-sm font-medium">{linear.workspace_name}</span>
              )}
            </div>
            <p className="text-destructive text-sm">
              {linear?.auth_error ??
                "Ingestion could not authenticate Linear. Reconnect to refresh tokens."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={onConnect}
                disabled={opening}
                analyticsName="linear_reconnect"
              >
                {opening ? "Opening…" : "Reconnect Linear"}
              </Button>
              <Button
                variant="outline"
                onClick={onCheck}
                disabled={check.status === "checking"}
                analyticsName="linear_check"
              >
                {check.status === "checking" ? "Checking…" : "I've connected it"}
              </Button>
            </div>
            <div className="text-muted-foreground space-y-2 text-sm">
              <p>
                If Linear says the app is already installed, revoke it first so OAuth
                can issue a new token:
              </p>
              <ol className="list-decimal space-y-1 pl-5">
                <li>
                  In Linear, open{" "}
                  <span className="font-medium">Settings → Installed Applications</span>
                </li>
                <li>
                  Find Propel → <span className="font-medium">Manage</span> →{" "}
                  <span className="font-medium">Revoke Access</span>
                </li>
                <li>Return here and click Reconnect Linear</li>
              </ol>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="text-muted-foreground text-sm">Not connected yet.</p>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={onConnect}
                disabled={opening}
                analyticsName="linear_connect"
              >
                {opening ? "Opening…" : "Connect Linear"}
              </Button>
              <Button
                variant="outline"
                onClick={onCheck}
                disabled={check.status === "checking"}
                analyticsName="linear_check"
              >
                {check.status === "checking" ? "Checking…" : "I've connected it"}
              </Button>
            </div>
          </div>
        )}
        {check.status === "not-found" && !hasAuthIssue && (
          <div className="text-muted-foreground space-y-2 text-sm">
            <p>
              Linear didn&apos;t finish authorizing — this usually means the app is
              already installed and Linear skipped the OAuth callback.
            </p>
            <ol className="list-decimal space-y-1 pl-5">
              <li>
                In Linear, open{" "}
                <span className="font-medium">Settings → Installed Applications</span>
              </li>
              <li>
                Find Propel → <span className="font-medium">Manage</span> →{" "}
                <span className="font-medium">Revoke Access</span>
              </li>
              <li>Return here and click Connect Linear again</li>
            </ol>
          </div>
        )}
        {check.status === "error" && (
          <p className="text-destructive text-sm">{check.message}</p>
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
