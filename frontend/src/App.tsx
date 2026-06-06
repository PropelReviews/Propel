import { useEffect } from "react";
import { usePostHog } from "posthog-js/react";
import { Button } from "@/components/ui/button";

function App() {
  const posthog = usePostHog();

  useEffect(() => {
    posthog?.capture("homepage_viewed");
  }, [posthog]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Propel</h1>
      <p className="text-muted-foreground max-w-md text-center">
        Open source developer analytics for teams that want to trust their
        metrics.
      </p>
      <Button>Get Started</Button>
    </main>
  );
}

export default App;
