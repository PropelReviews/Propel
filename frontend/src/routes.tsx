import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import App from "@/App";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { useChartDemoFlag } from "@/hooks/use-chart-demo-flag";
import { ChartDemoPage } from "@/pages/chart-demo";
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

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
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
