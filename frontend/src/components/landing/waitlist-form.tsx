import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check } from "lucide-react";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, joinWaitlist } from "@/lib/api";
import { cn } from "@/lib/utils";

const waitlistSchema = z.object({
  email: z.string().email("Enter a valid email address."),
});

type WaitlistValues = z.infer<typeof waitlistSchema>;

/**
 * Email capture shown in place of the cloud CTAs while the `signup-signin`
 * flag is off. `inline` centers itself for the hero; `card` stretches to fill
 * a card footer.
 */
export function WaitlistForm({
  variant = "inline",
  className,
}: {
  variant?: "inline" | "card";
  className?: string;
}) {
  const [submitted, setSubmitted] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<WaitlistValues>({
    resolver: zodResolver(waitlistSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = async (values: WaitlistValues) => {
    setServerError(null);
    try {
      await joinWaitlist(values);
      setSubmitted(true);
    } catch (error) {
      if (error instanceof ApiError && error.code === "WAITLIST_EMAIL_ALREADY_EXISTS") {
        // Already subscribed reads as success to the visitor.
        setSubmitted(true);
        return;
      }
      setServerError(
        error instanceof ApiError
          ? error.message
          : "Something went wrong. Please try again.",
      );
    }
  };

  if (submitted) {
    return (
      <p
        className={cn(
          "text-muted-foreground flex items-center gap-2 text-sm",
          variant === "inline" && "justify-center",
          className,
        )}
      >
        <Check className="text-primary size-4 shrink-0" />
        You're on the list — we'll let you know when Propel Cloud opens up.
      </p>
    );
  }

  const emailError = errors.email?.message ?? serverError;

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className={cn(
        "flex w-full flex-col gap-2",
        variant === "inline" && "max-w-md",
        className,
      )}
      noValidate
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          type="email"
          placeholder="you@company.com"
          aria-label="Email address"
          autoComplete="email"
          aria-invalid={Boolean(emailError)}
          {...register("email")}
        />
        <Button
          type="submit"
          disabled={isSubmitting}
          analyticsName="waitlist_submit"
          className="shrink-0"
        >
          {isSubmitting ? "Joining..." : "Join the waitlist"}
        </Button>
      </div>
      {emailError && (
        <p role="alert" className="text-destructive text-sm">
          {emailError}
        </p>
      )}
    </form>
  );
}
