import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/providers/auth-provider";

const ERROR_MESSAGES: Record<string, string> = {
  github_login_failed: "GitHub sign-in could not be completed. Please try again.",
  account_inactive: "Your account is inactive. Contact your administrator.",
};

/**
 * Lands here after the GitHub OAuth backend callback redirects with the session
 * token (or an error) in the URL fragment. Establishes the session and forwards
 * to the home page, stripping the token from the URL/history.
 */
export function GithubCallbackPage() {
  const navigate = useNavigate();
  const { signInWithToken } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const token = params.get("access_token");
    const errCode = params.get("error");

    // Drop the token from the address bar / history immediately.
    window.history.replaceState(null, "", window.location.pathname);

    void (async () => {
      if (errCode) {
        setError(ERROR_MESSAGES[errCode] ?? "GitHub sign-in failed. Please try again.");
        return;
      }
      if (!token) {
        setError("No sign-in token was returned. Please try again.");
        return;
      }
      try {
        await signInWithToken(token);
        navigate("/", { replace: true });
      } catch {
        setError("Could not establish your session. Please try signing in again.");
      }
    })();
  }, [navigate, signInWithToken]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center p-8">
      {error ? (
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Sign-in failed</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              to="/signin"
              className="text-foreground text-sm underline underline-offset-4"
            >
              Back to sign in
            </Link>
          </CardContent>
        </Card>
      ) : (
        <p className="text-muted-foreground text-sm">Finishing GitHub sign-in…</p>
      )}
    </main>
  );
}
