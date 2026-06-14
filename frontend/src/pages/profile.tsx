import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { GithubIcon } from "@/components/landing/github-icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError, getGithubLinkUrl } from "@/lib/api";
import { useAuth } from "@/providers/auth-provider";

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function ProfilePage() {
  const navigate = useNavigate();
  const { status, user, refreshUser } = useAuth();
  const [params, setParams] = useSearchParams();
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<"connected" | "error" | null>(null);

  useEffect(() => {
    if (status === "anonymous") navigate("/signin", { replace: true });
  }, [status, navigate]);

  // Handle the redirect back from GitHub (`?github=connected` / `?github=error`).
  useEffect(() => {
    const result = params.get("github");
    if (result !== "connected" && result !== "error") return;
    void (async () => {
      if (result === "connected") {
        await refreshUser();
        setNotice("connected");
      } else {
        setNotice("error");
      }
    })();
    const next = new URLSearchParams(params);
    next.delete("github");
    setParams(next, { replace: true });
  }, [params, refreshUser, setParams]);

  const onConnect = async () => {
    setError(null);
    setConnecting(true);
    try {
      const url = await getGithubLinkUrl();
      window.location.href = url;
    } catch (err) {
      setConnecting(false);
      setError(
        err instanceof ApiError
          ? err.status === 503
            ? "GitHub sign-in isn't configured for this deployment yet."
            : err.message
          : "Could not start GitHub connection. Please try again.",
      );
    }
  };

  if (status === "loading" || status === "anonymous") {
    return (
      <main className="flex min-h-svh items-center justify-center p-8">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    );
  }

  const github = user?.github;
  const connected = Boolean(github?.connected);

  return (
    <main className="bg-background mx-auto min-h-svh max-w-2xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Profile</h1>
        <p className="text-muted-foreground mt-2">
          Manage your Propel account and connected identities.
        </p>
      </header>

      {notice === "connected" && (
        <p
          role="status"
          className="mb-6 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700 dark:text-emerald-400"
        >
          GitHub connected. We&apos;ve linked your account and synced your organization
          memberships.
        </p>
      )}
      {notice === "error" && (
        <p
          role="alert"
          className="border-destructive/30 bg-destructive/10 text-destructive mb-6 rounded-lg border px-3 py-2 text-sm"
        >
          We couldn&apos;t complete the GitHub connection. Please try again.
        </p>
      )}

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>Your Propel account details.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <Row label="Name" value={user?.name ?? "—"} />
            <Row label="Email" value={user?.email ?? "—"} />
            <Row label="Member since" value={formatDate(user?.created_at)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GithubIcon className="size-5" />
              GitHub
            </CardTitle>
            <CardDescription>
              Connect your GitHub account so Propel can link you to your organization
              and attribute your work.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {connected ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">Connected</Badge>
                    {github?.login && (
                      <span className="text-sm font-medium">@{github.login}</span>
                    )}
                  </div>
                  {github?.account_email && (
                    <span className="text-muted-foreground text-xs">
                      {github.account_email}
                    </span>
                  )}
                </div>
                <Button
                  variant="outline"
                  onClick={onConnect}
                  disabled={connecting}
                  analyticsName="github_reconnect"
                >
                  <GithubIcon />
                  {connecting ? "Redirecting…" : "Reconnect"}
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <p className="text-muted-foreground text-sm">Not connected yet.</p>
                <Button
                  onClick={onConnect}
                  disabled={connecting}
                  analyticsName="github_connect"
                  className="self-start"
                >
                  <GithubIcon />
                  {connecting ? "Redirecting…" : "Connect with GitHub"}
                </Button>
              </div>
            )}
            {error && <p className="text-destructive text-sm">{error}</p>}
          </CardContent>
        </Card>

        <div>
          <Button asChild variant="ghost" analyticsName="profile_back_home">
            <Link to="/">← Back home</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
