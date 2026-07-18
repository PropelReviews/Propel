import { useFeatureFlagEnabled } from "posthog-js/react";

import { isPostHogEnabled } from "@/providers/posthog-provider";

export const LANDING_BLOG_FEATURE_FLAG = "landing-blog";

/**
 * Whether the marketing blog (`/blog`) should be shown.
 *
 * Primary control is the PostHog feature flag `landing-blog`. When PostHog is
 * disabled (no key — e.g. a keyless self-host), the flag is unavailable, so we
 * fall back to the build-time `VITE_LANDING_BLOG_ENABLED` env (default off).
 */
export function useLandingBlogFlag(): boolean {
  const flagEnabled = useFeatureFlagEnabled(LANDING_BLOG_FEATURE_FLAG, false);

  if (!isPostHogEnabled) {
    return import.meta.env.VITE_LANDING_BLOG_ENABLED === "true";
  }

  return flagEnabled === true;
}
