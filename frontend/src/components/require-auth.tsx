import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "@/providers/auth-provider";

/** Redirects anonymous users to sign-in, preserving the intended location. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <main className="flex min-h-svh items-center justify-center p-8">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    );
  }
  if (status === "anonymous") {
    return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  }
  return children;
}
