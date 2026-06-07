import { useFeatureFlagEnabled } from "posthog-js/react";

import { isPostHogEnabled } from "@/providers/posthog-provider";

export const CHART_DEMO_FEATURE_FLAG = "chart-demo";

/**
 * Whether the chart library demo (`/dev/charts`) should be exposed.
 *
 * Primary control is the PostHog feature flag `chart-demo`. When PostHog is
 * disabled (no key — e.g. a keyless self-host), the flag is unavailable, so we
 * fall back to the build-time `VITE_CHART_DEMO_ENABLED` env (default off). This
 * keeps the demo hidden by default until explicitly turned on.
 */
export function useChartDemoFlag(): boolean {
  // Default false so unresolved/disabled flags hide the demo.
  const flagEnabled = useFeatureFlagEnabled(CHART_DEMO_FEATURE_FLAG, false);

  if (!isPostHogEnabled) {
    return import.meta.env.VITE_CHART_DEMO_ENABLED === "true";
  }

  return flagEnabled === true;
}
