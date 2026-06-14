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
import { HomePage } from "@/pages/home";
import { InviteAcceptPage } from "@/pages/invites/accept";
import { ProfilePage } from "@/pages/profile";
import { AccessPage } from "@/pages/settings/access";
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
      <Route path="/auth/callback" element={<Navigate to="/" replace />} />
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
