import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";

import { SignUpForm } from "@/components/auth/sign-up-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/providers/auth-provider";

export function SignUpPage() {
  const navigate = useNavigate();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "authenticated") navigate("/", { replace: true });
  }, [status, navigate]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center p-8">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Create your account</CardTitle>
          <CardDescription>Start trusting your engineering metrics.</CardDescription>
        </CardHeader>
        <CardContent>
          <SignUpForm onSuccess={() => navigate("/", { replace: true })} />
        </CardContent>
        <CardFooter className="text-muted-foreground justify-center text-sm">
          <span>
            Already have an account?{" "}
            <Link to="/signin" className="text-foreground underline underline-offset-4">
              Sign in
            </Link>
          </span>
        </CardFooter>
      </Card>
    </main>
  );
}
