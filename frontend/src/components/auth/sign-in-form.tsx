import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";

export function SignInForm({ onSuccess }: { onSuccess?: () => void }) {
  const { signIn, status } = useAuth();

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Sign-in is handled by our identity provider. You&apos;ll be redirected to create
        an account or sign in with email, password, MFA, or passkeys.
      </p>
      <Button
        type="button"
        size="lg"
        disabled={status === "loading"}
        analyticsName="auth_submit_signin"
        onClick={() => {
          signIn();
          onSuccess?.();
        }}
      >
        Continue to sign in
      </Button>
    </div>
  );
}
