import { useState } from "react";

import { GithubIcon } from "@/components/landing/github-icon";
import { Button } from "@/components/ui/button";
import { ApiError, getGithubLoginUrl } from "@/lib/api";

/** "or" separator between password auth and OAuth on the auth screens. */
export function AuthDivider() {
  return (
    <div className="flex items-center gap-3" aria-hidden="true">
      <span className="bg-border h-px flex-1" />
      <span className="text-muted-foreground text-xs">or</span>
      <span className="bg-border h-px flex-1" />
    </div>
  );
}

/**
 * "Continue with GitHub" button used on the sign-in and sign-up screens. Fetches
 * the GitHub authorization URL and performs a full-page redirect; the backend
 * callback returns to `/auth/github/callback` with a session token.
 */
export function GithubAuthButton({
  label = "Continue with GitHub",
}: {
  label?: string;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onClick = async () => {
    setError(null);
    setLoading(true);
    try {
      const url = await getGithubLoginUrl();
      window.location.href = url;
    } catch (err) {
      setLoading(false);
      setError(
        err instanceof ApiError && err.status === 503
          ? "GitHub sign-in isn't configured for this deployment yet."
          : "Could not start GitHub sign-in. Please try again.",
      );
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        variant="outline"
        size="lg"
        onClick={onClick}
        disabled={loading}
        analyticsName="auth_github"
      >
        <GithubIcon />
        {loading ? "Redirecting…" : label}
      </Button>
      {error && <p className="text-destructive text-sm">{error}</p>}
    </div>
  );
}
