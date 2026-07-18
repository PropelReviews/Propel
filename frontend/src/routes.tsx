import type { ReactNode } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import App from "@/App";
import { AppShell } from "@/components/app-shell";
import { RequireAuth } from "@/components/require-auth";
import { RequirePermission } from "@/components/require-permission";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { useChartDemoFlag } from "@/hooks/use-chart-demo-flag";
import { ChartDemoPage } from "@/pages/chart-demo";
import { GithubCallbackPage } from "@/pages/github-callback";
import { HomePage } from "@/pages/home";
import { InviteAcceptPage } from "@/pages/invites/accept";
import { ProfilePage } from "@/pages/profile";
import { MetricsPage } from "@/pages/metrics";
import { MetricDetailRoute } from "@/pages/metrics/detail";
import { MetricEditPage } from "@/pages/metrics/edit";
import { MetricNewPage } from "@/pages/metrics/new";
import { DimensionMappingsSettingsPage } from "@/pages/settings/dimension-mappings";
import { WorkspacePage } from "@/pages/settings/workspace";
import { SignInPage } from "@/pages/sign-in";
import { SignUpPage } from "@/pages/sign-up";

/** Gates auth routes behind the `signup-signin` feature flag. */
function RequireAuthFlag({ children }: { children: ReactNode }) {
  const authEnabled = useAuthFlag();
  if (!authEnabled) return <Navigate to="/" replace />;
  return children;
}

/** Gates the chart demo route behind the `chart-demo` feature flag. */
function RequireChartDemoFlag({ children }: { children: ReactNode }) {
  const chartDemoEnabled = useChartDemoFlag();
  if (!chartDemoEnabled) return <Navigate to="/" replace />;
  return children;
}

/** App pages share the header shell (nav, workspace switcher). */
function ShellLayout() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route element={<ShellLayout />}>
        <Route path="/home" element={<HomePage />} />
        {/* The Data page is gone; keep old bookmarks working. */}
        <Route path="/data" element={<Navigate to="/home" replace />} />
        <Route
          path="/metrics"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:read"]}>
                <MetricsPage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        <Route
          path="/metrics/new"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:manage"]}>
                <MetricNewPage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        <Route
          path="/metrics/:metricId/edit"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:manage"]}>
                <MetricEditPage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        <Route
          path="/metrics/:metricId"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:read"]}>
                <MetricDetailRoute />
              </RequirePermission>
            </RequireAuth>
          }
        />
        {/* Access management now lives on the Account page. */}
        <Route path="/settings/access" element={<Navigate to="/profile" replace />} />
        <Route
          path="/settings/workspace"
          element={
            <RequireAuth>
              {/* Hosts integrations (connections:manage) and metric health
                  (metrics:read); sections gate themselves. */}
              <RequirePermission anyOf={["connections:manage", "metrics:read"]}>
                <WorkspacePage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        {/* The Metric set page is gone; enable/disable + params now happen
            from the Metrics catalog. */}
        <Route
          path="/settings/metric-set"
          element={<Navigate to="/metrics" replace />}
        />
        <Route
          path="/settings/dimension-mappings"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:read"]}>
                <DimensionMappingsSettingsPage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        {/* Metric health merged into the Workspace page. */}
        <Route
          path="/settings/metric-health"
          element={<Navigate to="/settings/workspace" replace />}
        />
        <Route
          path="/profile"
          element={
            <RequireAuthFlag>
              <ProfilePage />
            </RequireAuthFlag>
          }
        />
      </Route>
      <Route
        path="/invites/:token/accept"
        element={
          <RequireAuth>
            <InviteAcceptPage />
          </RequireAuth>
        }
      />
      <Route
        path="/signin"
        element={
          <RequireAuthFlag>
            <SignInPage />
          </RequireAuthFlag>
        }
      />
      <Route
        path="/signup"
        element={
          <RequireAuthFlag>
            <SignUpPage />
          </RequireAuthFlag>
        }
      />
      <Route
        path="/auth/github/callback"
        element={
          <RequireAuthFlag>
            <GithubCallbackPage />
          </RequireAuthFlag>
        }
      />
      <Route
        path="/dev/charts"
        element={
          <RequireChartDemoFlag>
            <ChartDemoPage />
          </RequireChartDemoFlag>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
