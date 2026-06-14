import { useEffect } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { AuthRedirectForm } from "@/components/auth/auth-redirect-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/providers/auth-provider";

export function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { status } = useAuth();
  const errorCode = searchParams.get("error");
  // Where to land after sign-in (e.g. an invite accept link set by RequireAuth).
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  useEffect(() => {
    if (status === "authenticated") navigate(from, { replace: true });
  }, [status, navigate, from]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Welcome back</CardTitle>
          <CardDescription>Sign in to your Propel account.</CardDescription>
        </CardHeader>
        <CardContent>
          <AuthRedirectForm
            errorCode={errorCode}
            onSuccess={() => navigate(from, { replace: true })}
          />
        </CardContent>
      </Card>
    </main>
  );
}
