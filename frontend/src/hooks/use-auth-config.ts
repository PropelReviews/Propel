import { useEffect, useRef, useState } from "react";

import { ApiError, getAuthConfig, redirectToLogin, type AuthConfig } from "@/lib/api";

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  oidc_failed: "Sign-in failed. Please try again.",
  missing_claims: "Your account is missing required profile information.",
};

export function authErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return AUTH_ERROR_MESSAGES[code] ?? "Sign-in failed. Please try again.";
}

type AuthRedirectState = {
  config: AuthConfig | null;
  loading: boolean;
  redirecting: boolean;
  error: string | null;
  startRedirect: () => void;
};

export function useAuthRedirect(errorCode: string | null): AuthRedirectState {
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [redirecting, setRedirecting] = useState(false);
  const [error, setError] = useState<string | null>(authErrorMessage(errorCode));
  const autoRedirectStarted = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await getAuthConfig();
        if (!cancelled) {
          setConfig(next);
          if (!next.oidc_enabled) {
            setError("Sign-in is not configured yet.");
          } else if (!errorCode && !autoRedirectStarted.current) {
            autoRedirectStarted.current = true;
            setRedirecting(true);
            redirectToLogin(next.login_url);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : "Unable to load sign-in configuration.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [errorCode]);

  const startRedirect = () => {
    if (!config?.oidc_enabled) return;
    setRedirecting(true);
    redirectToLogin(config.login_url);
  };

  return { config, loading, redirecting, error, startRedirect };
}
