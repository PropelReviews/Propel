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
