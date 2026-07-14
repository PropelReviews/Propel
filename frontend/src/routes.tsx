import type { ReactNode } from "react";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import App from "@/App";
import { AppShell } from "@/components/app-shell";
import { RequireAuth } from "@/components/require-auth";
import { RequirePermission } from "@/components/require-permission";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { useChartDemoFlag } from "@/hooks/use-chart-demo-flag";
import { ChartDemoPage } from "@/pages/chart-demo";
import { DataPage } from "@/pages/data";
import { GithubCallbackPage } from "@/pages/github-callback";
import { HomePage } from "@/pages/home";
import { InviteAcceptPage } from "@/pages/invites/accept";
import { ProfilePage } from "@/pages/profile";
import { MetricsPage } from "@/pages/metrics";
import { MetricDetailRoute } from "@/pages/metrics/detail";
import { MetricEditPage } from "@/pages/metrics/edit";
import { MetricNewPage } from "@/pages/metrics/new";
import { AccessPage } from "@/pages/settings/access";
import { DimensionMappingsSettingsPage } from "@/pages/settings/dimension-mappings";
import { MetricHealthSettingsPage } from "@/pages/settings/metric-health";
import { MetricSetPage } from "@/pages/settings/metric-set";
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
        <Route path="/data" element={<DataPage />} />
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
        <Route
          path="/settings/access"
          element={
            <RequireAuth>
              <RequirePermission
                anyOf={["roles:manage", "members:assign_role", "invites:read"]}
              >
                <AccessPage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        <Route
          path="/settings/workspace"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["connections:manage"]}>
                <WorkspacePage />
              </RequirePermission>
            </RequireAuth>
          }
        />
        <Route
          path="/settings/metric-set"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:read"]}>
                <MetricSetPage />
              </RequirePermission>
            </RequireAuth>
          }
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
        <Route
          path="/settings/metric-health"
          element={
            <RequireAuth>
              <RequirePermission anyOf={["metrics:read"]}>
                <MetricHealthSettingsPage />
              </RequirePermission>
            </RequireAuth>
          }
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
