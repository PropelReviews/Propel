type PostHogErrorFallbackProps = {
  error: unknown;
};

export function PostHogErrorFallback({ error }: PostHogErrorFallbackProps) {
  const message =
    error instanceof Error ? error.message : "Something went wrong.";

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-xl font-semibold tracking-tight">
        Something went wrong
      </h1>
      <p className="text-muted-foreground max-w-md text-center text-sm">
        {message}
      </p>
      <button
        type="button"
        className="text-sm underline underline-offset-4"
        onClick={() => window.location.reload()}
      >
        Reload page
      </button>
    </main>
  );
}
