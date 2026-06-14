import { AuthRedirectForm } from "@/components/auth/auth-redirect-form";

export function SignUpForm({ onSuccess }: { onSuccess?: () => void }) {
  return <AuthRedirectForm action="sign-up" onSuccess={onSuccess} />;
}
