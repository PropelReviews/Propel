import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

/** Placeholder until M5.2 simple builder ships. */
export function MetricBuilderPlaceholder({ mode }: { mode: "create" | "edit" }) {
  return (
    <main className="bg-background mx-auto min-h-svh max-w-2xl px-6 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">
        {mode === "create" ? "New metric" : "Edit metric"}
      </h1>
      <p className="text-muted-foreground mt-3 text-sm">
        The structured builder (sections ①–⑦, YAML toggle, draft autosave) lands in
        M5.2. Until then, create drafts via{" "}
        <code className="bg-muted rounded px-1">POST …/metric-definitions</code> or the
        push CLI.
      </p>
      <Button asChild variant="outline" className="mt-6">
        <Link to="/metrics">Back to catalog</Link>
      </Button>
    </main>
  );
}
