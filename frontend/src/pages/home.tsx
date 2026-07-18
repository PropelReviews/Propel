import { Link } from "react-router-dom";

import { ConnectTools } from "@/components/connect-tools";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { MyMetricsDashboard } from "@/features/my-metrics/my-metrics-dashboard";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

export function HomePage() {
  const { status: authStatus, user } = useAuth();
  const { tenant, status: tenantStatus, refresh } = useTenant();

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
        <ConnectTools onConnected={() => void refresh()} />
      </Page>
    );
  }

  const firstName = user?.name?.split(" ")[0];

  return (
    <Page
      title="My metrics"
      subtitle="Your personal contribution metrics — add or remove charts to taste."
      greeting={firstName ? `Welcome back, ${firstName}.` : undefined}
    >
      {user && (
        // Keyed so a user/workspace switch reloads that dashboard's layout.
        <MyMetricsDashboard
          key={`${user.id}:${tenant.id}`}
          userId={user.id}
          tenantId={tenant.id}
        />
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
