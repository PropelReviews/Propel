import { lazy, Suspense } from "react";

const LazyEditor = lazy(() => import("@monaco-editor/react"));

type Props = {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
  height?: string;
};

/** Monaco YAML editor (lazy-loaded so form mode stays light). */
export function MetricYamlEditor({
  value,
  onChange,
  readOnly = false,
  height = "28rem",
}: Props) {
  return (
    <div
      className="border-border overflow-hidden rounded-lg border"
      data-testid="metric-yaml-editor"
    >
      <Suspense
        fallback={
          <textarea
            className="bg-background min-h-64 w-full p-3 font-mono text-sm"
            value={value}
            readOnly={readOnly}
            onChange={(e) => onChange(e.target.value)}
            aria-label="Metric YAML loading"
          />
        }
      >
        <LazyEditor
          height={height}
          defaultLanguage="yaml"
          theme="vs-dark"
          value={value}
          onChange={(v) => onChange(v ?? "")}
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            tabSize: 2,
            automaticLayout: true,
          }}
        />
      </Suspense>
    </div>
  );
}
