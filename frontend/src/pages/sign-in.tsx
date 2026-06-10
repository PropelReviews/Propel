import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { SignInForm } from "@/components/auth/sign-in-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/providers/auth-provider";

export function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { status } = useAuth();
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
          <SignInForm onSuccess={() => navigate(from, { replace: true })} />
        </CardContent>
        <CardFooter className="text-muted-foreground justify-center text-sm">
          <span>
            Don&apos;t have an account?{" "}
            <Link to="/signup" className="text-foreground underline underline-offset-4">
              Sign up
            </Link>
          </span>
        </CardFooter>
      </Card>
    </main>
  );
}
