import { PostHogProvider as PHProvider } from "posthog-js/react";
import posthog from "posthog-js";
import type { ReactNode } from "react";

const posthogKey = import.meta.env.VITE_POSTHOG_KEY;
const posthogHost =
  import.meta.env.VITE_POSTHOG_HOST ?? "https://us.i.posthog.com";

const isPostHogEnabled = Boolean(posthogKey);

if (isPostHogEnabled && !posthog.__loaded) {
  posthog.init(posthogKey!, {
    api_host: posthogHost,
    person_profiles: "identified_only",
    autocapture: true, // intentional: capture all element clicks
    capture_pageview: true, // explicit (switch to "history_change" when a router is added)
    capture_pageleave: true,
    loaded: (ph) => {
      ph.register({
        app_environment: import.meta.env.VITE_APP_ENV ?? import.meta.env.MODE,
        app_version: import.meta.env.VITE_APP_VERSION ?? "0.0.0",
        git_sha: import.meta.env.VITE_GIT_SHA ?? "dev",
      });
    },
  });
}

type PostHogProviderProps = {
  children: ReactNode;
};

export function PostHogProvider({ children }: PostHogProviderProps) {
  if (!isPostHogEnabled) {
    return children;
  }

  return <PHProvider client={posthog}>{children}</PHProvider>;
}

export { posthog, isPostHogEnabled };
