import { useEffect } from "react";
import { usePostHog } from "posthog-js/react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuthFlag } from "@/hooks/use-auth-flag";
import { useChartDemoFlag } from "@/hooks/use-chart-demo-flag";
import { useAuth } from "@/providers/auth-provider";

function App() {
  const posthog = usePostHog();
  const authEnabled = useAuthFlag();
  const chartDemoEnabled = useChartDemoFlag();
  const { status, user, signOut } = useAuth();

  useEffect(() => {
    posthog?.capture("homepage_viewed");
  }, [posthog]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Propel</h1>
      <p className="text-muted-foreground max-w-md text-center">
        Open source developer analytics for teams that want to trust their metrics.
      </p>

      {authEnabled && status === "loading" ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : authEnabled && status === "authenticated" ? (
        <div className="flex flex-col items-center gap-3">
          <p className="text-muted-foreground text-sm">
            Signed in as {user?.name ?? user?.email}
          </p>
          <div className="flex items-center gap-3">
            <Button asChild analyticsName="nav_data">
              <Link to="/data">View data</Link>
            </Button>
            <Button variant="outline" analyticsName="sign_out" onClick={signOut}>
              Sign out
            </Button>
          </div>
        </div>
      ) : authEnabled ? (
        <div className="flex items-center gap-3">
          <Button asChild analyticsName="get_started">
            <Link to="/signup">Get Started</Link>
          </Button>
          <Button asChild variant="outline" analyticsName="nav_sign_in">
            <Link to="/signin">Sign in</Link>
          </Button>
        </div>
      ) : (
        <Button analyticsName="get_started">Get Started</Button>
      )}

      {chartDemoEnabled && (
        <Link
          to="/dev/charts"
          className="text-muted-foreground hover:text-foreground text-sm underline underline-offset-4"
        >
          Chart library demo
        </Link>
      )}
    </main>
  );
}

export default App;
