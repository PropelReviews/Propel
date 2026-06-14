import { Button } from "@/components/ui/button";
import { useAuth } from "@/providers/auth-provider";

export function SignUpForm({ onSuccess }: { onSuccess?: () => void }) {
  const { signUp, status } = useAuth();

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-sm">
        Create your account through our hosted sign-up flow. Email verification,
        password reset, and MFA are handled there.
      </p>
      <Button
        type="button"
        size="lg"
        disabled={status === "loading"}
        analyticsName="auth_submit_signup"
        onClick={() => {
          signUp();
          onSuccess?.();
        }}
      >
        Continue to sign up
      </Button>
    </div>
  );
}
