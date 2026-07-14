import { useState } from "react";

import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { ApiError } from "@/lib/api";
import {
  previewMetricDefinition,
  type PreviewResponse,
} from "@/features/metrics/api/metric-definitions";
import { documentToYaml } from "@/features/metrics/document/yaml-io";

export function PreviewPanel({
  token,
  tenantId,
  doc,
}: {
  token: string;
  tenantId: string;
  doc: Record<string, unknown>;
}) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await previewMetricDefinition(token, tenantId, documentToYaml(doc));
      setResult(res);
    } catch (err) {
      setResult(null);
      setError(err instanceof ApiError ? err.message : "Preview failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <aside
      className="border-border bg-muted/20 space-y-3 rounded-lg border p-4"
      data-testid="preview-panel"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-medium">Preview</h2>
        <Button size="sm" disabled={loading} onClick={() => void run()}>
          {loading ? "Running…" : "Run preview"}
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-destructive text-sm">
          {error}
        </p>
      )}
      {result && (
        <div className="space-y-3 text-sm">
          <p className="text-muted-foreground text-xs">
            {result.timing_ms}ms · grain {result.grain ?? "—"} ·{" "}
            {result.executed ? "executed" : "dry-run SQL"}
            {result.sampled ? " · sampled estimate" : ""}
          </p>
          {result.diagnostics.map((d, i) => (
            <p key={i} className="text-muted-foreground text-xs">
              {String(d.message ?? JSON.stringify(d))}
            </p>
          ))}
          {result.rows.length === 0 ? (
            <p className="text-muted-foreground text-xs">
              No sample rows returned. Inspect generated SQL below.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr>
                    {Object.keys(result.rows[0]!).map((k) => (
                      <th key={k} className="border-b px-2 py-1 font-medium">
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.slice(0, 20).map((row, i) => (
                    <tr key={i}>
                      {Object.keys(result.rows[0]!).map((k) => (
                        <td key={k} className="border-b px-2 py-1 font-mono">
                          {String(row[k] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <details>
            <summary className="cursor-pointer text-xs font-medium">
              Generated SQL
            </summary>
            <CodeBlock code={result.sql} className="mt-2 max-h-64 overflow-auto" />
          </details>
        </div>
      )}
    </aside>
  );
}
