import { AuthRedirectForm } from "@/components/auth/auth-redirect-form";

export function SignInForm({
  errorCode,
  onSuccess,
}: {
  errorCode?: string | null;
  onSuccess?: () => void;
}) {
  return (
    <AuthRedirectForm action="sign-in" errorCode={errorCode} onSuccess={onSuccess} />
  );
}
