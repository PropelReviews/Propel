import { PostHogErrorBoundary, PostHogProvider as PHProvider } from "posthog-js/react";
import posthog from "posthog-js";
import type { ReactNode } from "react";

import { PostHogErrorFallback } from "@/components/posthog-error-fallback";
import {
  readCachedDistinctId,
  readCachedFeatureFlags,
  writeCachedFeatureFlags,
} from "@/lib/posthog-persistence";

const posthogKey = import.meta.env.VITE_POSTHOG_KEY;
const posthogHost =
  import.meta.env.VITE_POSTHOG_HOST ?? "https://metrics.propelreview.com";
const posthogUiHost = import.meta.env.VITE_POSTHOG_UI_HOST ?? "https://us.posthog.com";

const isPostHogEnabled = Boolean(posthogKey);

if (isPostHogEnabled && !posthog.__loaded) {
  const { distinctId, isIdentified } = readCachedDistinctId();

  posthog.init(posthogKey!, {
    api_host: posthogHost,
    ui_host: posthogUiHost,
    person_profiles: "identified_only",
    autocapture: true, // intentional: capture all element clicks
    capture_pageview: "history_change",
    capture_pageleave: true,
    // Only capture exceptions in real (built) environments. In `vite dev`,
    // exceptions are dominated by dev-only tooling noise — most notably Vite's
    // own HMR client (`/@vite/client`), which throws "WebSocket closed without
    // opened." whenever the dev server is reached over a non-localhost host.
    // Shipping those to error tracking creates false issues for the team.
    capture_exceptions: !import.meta.env.DEV,
    before_send: (event) => {
      // Belt-and-suspenders: drop any exception originating from Vite's HMR
      // client so dev tooling noise never reaches error tracking, even if
      // exception capture is somehow enabled in a dev-like build.
      if (event?.event === "$exception") {
        const frames = event.properties?.$exception_list ?? [];
        const isViteClient = frames.some(
          (entry: { stacktrace?: { frames?: { filename?: string }[] } }) =>
            entry?.stacktrace?.frames?.some((frame) =>
              frame?.filename?.includes("/@vite/client"),
            ),
        );
        if (isViteClient) {
          return null;
        }
      }
      return event;
    },
    session_recording: {
      maskAllInputs: true,
    },
    bootstrap: {
      featureFlags: readCachedFeatureFlags(),
      ...(distinctId ? { distinctID: distinctId, isIdentifiedID: isIdentified } : {}),
    },
    loaded: (ph) => {
      ph.register({
        app_environment: import.meta.env.VITE_APP_ENV ?? import.meta.env.MODE,
        app_version: import.meta.env.VITE_APP_VERSION ?? "0.0.0",
        git_sha: import.meta.env.VITE_GIT_SHA ?? "dev",
      });

      ph.onFeatureFlags((_flags, variants) => {
        writeCachedFeatureFlags(variants);
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

  return (
    <PHProvider client={posthog}>
      <PostHogErrorBoundary
        fallback={({ error }) => <PostHogErrorFallback error={error} />}
      >
        {children}
      </PostHogErrorBoundary>
    </PHProvider>
  );
}

export { posthog, isPostHogEnabled };
