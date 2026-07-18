import { useFeatureFlagEnabled } from "posthog-js/react";

import { isPostHogEnabled } from "@/providers/posthog-provider";

export const LANDING_CAREERS_FEATURE_FLAG = "landing-careers";

/**
 * Whether the marketing careers page (`/careers`) should be shown.
 *
 * Primary control is the PostHog feature flag `landing-careers`. When PostHog
 * is disabled (no key — e.g. a keyless self-host), the flag is unavailable, so
 * we fall back to the build-time `VITE_LANDING_CAREERS_ENABLED` env (default
 * off).
 */
export function useLandingCareersFlag(): boolean {
  const flagEnabled = useFeatureFlagEnabled(LANDING_CAREERS_FEATURE_FLAG, false);

  if (!isPostHogEnabled) {
    return import.meta.env.VITE_LANDING_CAREERS_ENABLED === "true";
  }

  return flagEnabled === true;
}
