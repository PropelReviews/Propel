import { Button } from "@/components/ui/button";
import { useAuthRedirect } from "@/hooks/use-auth-config";
import { useAuth } from "@/providers/auth-provider";

type AuthRedirectFormProps = {
  action: "sign-in" | "sign-up";
  errorCode?: string | null;
  onSuccess?: () => void;
};

export function AuthRedirectForm({
  action,
  errorCode = null,
  onSuccess,
}: AuthRedirectFormProps) {
  const { status } = useAuth();
  const { config, loading, redirecting, error, startRedirect } =
    useAuthRedirect(errorCode);
  const isSignIn = action === "sign-in";
  const showSetupHint = !loading && config !== null && !config.oidc_enabled;
  const showRetry = Boolean(errorCode) && config?.oidc_enabled;

  if (!loading && redirecting && config?.oidc_enabled && !errorCode) {
    return (
      <p className="text-muted-foreground text-sm">
        Redirecting to {isSignIn ? "sign in" : "sign up"}…
      </p>
    );
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
          analyticsName={isSignIn ? "auth_submit_signin" : "auth_submit_signup"}
          onClick={() => {
            startRedirect();
            onSuccess?.();
          }}
        >
          {isSignIn ? "Try signing in again" : "Try signing up again"}
        </Button>
      ) : null}
    </div>
  );
}
