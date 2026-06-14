import { Button } from "@/components/ui/button";
import { useAuthRedirect } from "@/hooks/use-auth-config";
import { useAuth } from "@/providers/auth-provider";

type AuthRedirectFormProps = {
  errorCode?: string | null;
  onSuccess?: () => void;
};

/**
 * Sign-in and sign-up both funnel through Zitadel's hosted login (Auth Code +
 * PKCE via the BFF), so a single redirect form backs both routes. It auto-
 * redirects when OIDC is configured and otherwise shows a local-setup hint or
 * a retry button after an error.
 */
export function AuthRedirectForm({
  errorCode = null,
  onSuccess,
}: AuthRedirectFormProps) {
  const { status } = useAuth();
  const { config, loading, redirecting, error, startRedirect } =
    useAuthRedirect(errorCode);
  const showSetupHint = !loading && config !== null && !config.oidc_enabled;
  const showRetry = Boolean(errorCode) && config?.oidc_enabled;

  if (!loading && redirecting && config?.oidc_enabled && !errorCode) {
    return <p className="text-muted-foreground text-sm">Redirecting to sign in…</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {showSetupHint ? (
        <p className="text-muted-foreground text-sm">
          Sign-in is not configured yet. Run{" "}
          <code className="text-foreground">docker compose up</code> (or{" "}
          <code className="text-foreground">./scripts/setup-zitadel-oidc.sh</code>
          ), then restart the backend.
        </p>
      ) : null}
      {error ? (
        <p className="text-destructive text-sm" role="alert">
          {error}
        </p>
      ) : null}
      {showRetry ? (
        <Button
          type="button"
          size="lg"
          disabled={status === "loading" || loading}
          analyticsName="auth_submit_signin"
          onClick={() => {
            startRedirect();
            onSuccess?.();
          }}
        >
          Try signing in again
        </Button>
      ) : null}
    </div>
  );
}
