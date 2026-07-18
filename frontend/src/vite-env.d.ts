/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_POSTHOG_KEY?: string;
  readonly VITE_POSTHOG_HOST?: string;
  readonly VITE_POSTHOG_UI_HOST?: string;
  readonly VITE_API_URL?: string;
  readonly VITE_APP_URL?: string;
  readonly VITE_GITHUB_URL?: string;
  readonly VITE_APP_ENV?: string;
  readonly VITE_APP_VERSION?: string;
  readonly VITE_GIT_SHA?: string;
  readonly VITE_AUTH_ENABLED?: string;
  readonly VITE_CHART_DEMO_ENABLED?: string;
  readonly VITE_LANDING_BLOG_ENABLED?: string;
  readonly VITE_LANDING_CAREERS_ENABLED?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
