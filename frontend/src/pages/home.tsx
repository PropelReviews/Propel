import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { formatCount } from "@/components/charts";
import { ConnectTools } from "@/components/connect-tools";
import { PrActivityChart } from "@/components/pr-activity-chart";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { getIngestionStats, type IngestionStats } from "@/lib/ingestion";
import type { Role } from "@/lib/permissions";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

type Scope = {
  title: string;
  subtitle: string;
};

// Manager teams aren't modeled yet, so a manager currently sees the same
// workspace-wide data as an admin, just framed as "your team".
const ROLE_SCOPE: Record<Role, Scope> = {
  owner: {
    title: "Organization",
    subtitle: "Engineering activity across your whole workspace.",
  },
  admin: {
    title: "Organization",
    subtitle: "Engineering activity across your whole workspace.",
  },
  manager: {
    title: "Your team",
    subtitle: "Engineering activity across your team.",
  },
  member: {
    title: "Your stats",
    subtitle: "Your personal contribution metrics.",
  },
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function HomePage() {
  const { status: authStatus, user } = useAuth();
  const { tenant, role, status: tenantStatus, refresh } = useTenant();
  const [reloadKey, setReloadKey] = useState(0);

  if (authStatus === "loading") {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (authStatus !== "authenticated") {
    return (
      <Page>
        <Card>
          <CardHeader>
            <CardTitle>Sign in required</CardTitle>
            <CardDescription>
              <Link to="/signin" className="underline underline-offset-4">
                Sign in
              </Link>{" "}
              to view your dashboard.
            </CardDescription>
          </CardHeader>
        </Card>
      </Page>
    );
  }

  if (tenantStatus === "idle" || tenantStatus === "loading") {
    return (
      <Page>
        <LoadingState />
      </Page>
    );
  }

  if (tenantStatus === "error") {
    return (
      <Page>
        <Card>
          <CardHeader>
            <CardTitle>Couldn’t load workspaces</CardTitle>
            <CardDescription>Please try again in a moment.</CardDescription>
          </CardHeader>
        </Card>
      </Page>
    );
  }

  // No workspace yet → drop the user straight into onboarding.
  if (!tenant) {
    return (
      <Page>
        <ConnectTools
          onConnected={() => {
            void refresh();
            setReloadKey((key) => key + 1);
          }}
        />
      </Page>
    );
  }

  const scope = role ? ROLE_SCOPE[role] : ROLE_SCOPE.member;
  const firstName = user?.name?.split(" ")[0];

  return (
    <Page
      title={scope.title}
      subtitle={scope.subtitle}
      greeting={firstName ? `Welcome back, ${firstName}.` : undefined}
    >
      {role === "member" ? (
        <PersonalStats />
      ) : (
        <WorkspaceStats key={reloadKey} tenantId={tenant.id} />
      )}
    </Page>
  );
}

function Page({
  title,
  subtitle,
  greeting,
  children,
}: {
  title?: string;
  subtitle?: string;
  greeting?: string;
  children: React.ReactNode;
}) {
  return (
    <main className="bg-background mx-auto min-h-svh max-w-6xl px-6 py-12">
      <header className="mb-10">
        {greeting && <p className="text-muted-foreground text-sm">{greeting}</p>}
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">
          {title ?? "Home"}
        </h1>
        {subtitle && <p className="text-muted-foreground mt-2 max-w-2xl">{subtitle}</p>}
      </header>
      {children}
    </main>
  );
}

function WorkspaceStats({ tenantId }: { tenantId: string }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "ready"; stats: IngestionStats }
    | { status: "error"; message: string }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setState({ status: "loading" });
      try {
        const stats = await getIngestionStats(tenantId);
        if (!cancelled) setState({ status: "ready", stats });
      } catch (error) {
        if (cancelled) return;
        const message =
          error instanceof ApiError ? error.message : "Could not load metrics.";
        setState({ status: "error", message });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "error") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Couldn’t load metrics</CardTitle>
          <CardDescription>{state.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const { stats } = state;
  return (
    <div className="space-y-12">
      <section>
        <h2 className="mb-4 text-lg font-medium">Overview</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Datapoints" value={stats.total_datapoints} />
          <StatCard label="Raw records" value={stats.total_raw_records} />
          <StatCard
            label="Sources"
            value={stats.by_source.length}
            hint={stats.by_source.map((s) => s.label).join(", ") || undefined}
          />
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Last sync</CardDescription>
              <CardTitle className="text-2xl tabular-nums">
                {formatTimestamp(stats.last_run_at)}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-medium">Pull request activity</h2>
        <PrActivityChart tenantId={tenantId} />
      </section>

      {stats.by_kind.length > 0 && (
        <section>
          <h2 className="mb-4 text-lg font-medium">Datapoints by kind</h2>
          <div className="flex flex-wrap gap-2">
            {stats.by_kind.map((row) => (
              <Badge key={row.label} variant="outline" className="gap-1.5">
                <span className="capitalize">{row.label}</span>
                <span className="text-muted-foreground tabular-nums">
                  {formatCount(row.count)}
                </span>
              </Badge>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function PersonalStats() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Personal stats are coming soon</CardTitle>
        <CardDescription>
          We&apos;re building per-developer metrics so you can track your own
          contributions. In the meantime, make sure your GitHub account is linked so we
          can attribute your work.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild variant="outline" analyticsName="home_link_profile">
          <Link to="/profile">Manage your GitHub connection</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-2xl tabular-nums">{formatCount(value)}</CardTitle>
      </CardHeader>
      {hint && (
        <CardContent>
          <p className="text-muted-foreground truncate text-xs">{hint}</p>
        </CardContent>
      )}
    </Card>
  );
}

function LoadingState() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}
