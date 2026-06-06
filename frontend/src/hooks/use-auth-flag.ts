import { useFeatureFlagEnabled } from "posthog-js/react";

import { isPostHogEnabled } from "@/providers/posthog-provider";

export const AUTH_FEATURE_FLAG = "signup-signin";

/**
 * Whether the sign up / sign in surface should be shown.
 *
 * Primary control is the PostHog feature flag `signup-signin`. When PostHog is
 * disabled (no key — e.g. a keyless self-host), the flag is unavailable, so we
 * fall back to the build-time `VITE_AUTH_ENABLED` env (default off). This keeps
 * auth hidden by default until it is explicitly turned on, without breaking
 * self-hosting.
 */
export function useAuthFlag(): boolean {
  const flagEnabled = useFeatureFlagEnabled(AUTH_FEATURE_FLAG);

  if (!isPostHogEnabled) {
    return import.meta.env.VITE_AUTH_ENABLED === "true";
  }

  return flagEnabled === true;
}
