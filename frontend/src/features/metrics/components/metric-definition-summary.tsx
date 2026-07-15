/**
 * Plain-language rendering of a Metric document, so nobody has to read raw
 * YAML to understand what a metric does.
 */

import type { ReactNode } from "react";

import { summarizeFilters } from "@/features/metrics/builder/filter-summary";
import { VisibilityBadge } from "@/features/metrics/components/metric-badges";

function humanizeEntity(entity: string): string {
  return entity.replace(/_/g, " ");
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function summarizeMeasure(measure: Record<string, unknown>, entity: string): string {
  const type = String(measure.type ?? "count");
  const noun = humanizeEntity(entity);
  switch (type) {
    case "count":
      return `Count of ${noun}s`;
    case "count_distinct":
      return `Count of distinct ${String(measure.field ?? "?")} values per ${noun}`;
    case "sum":
      return `Sum of ${String(measure.field ?? "?")} across ${noun}s`;
    case "avg":
      return `Average ${String(measure.field ?? "?")} per ${noun}`;
    case "min":
      return `Minimum ${String(measure.field ?? "?")} across ${noun}s`;
    case "max":
      return `Maximum ${String(measure.field ?? "?")} across ${noun}s`;
    case "percentile":
      return `Percentile of ${String(measure.field ?? "?")} across ${noun}s`;
    case "interval": {
      const agg = capitalize(String(measure.agg ?? "median"));
      return `${agg} time from ${String(measure.from ?? "?")} to ${String(
        measure.to ?? "?",
      )} per ${noun}`;
    }
    case "ratio": {
      const num = (measure.numerator ?? {}) as Record<string, unknown>;
      const den = (measure.denominator ?? {}) as Record<string, unknown>;
      return `Ratio of ${String(num.ref ?? "?")} to ${String(den.ref ?? "?")}`;
    }
    case "formula":
      return `Formula: ${String(measure.expr ?? "?")}`;
    case "sql":
      return "Raw SQL measure";
    default:
      return `${capitalize(type)} over ${noun}s`;
  }
}

function summarizeTime(time: Record<string, unknown>): string {
  const field = String(time.field ?? "?");
  const grains = Array.isArray(time.grains) ? (time.grains as string[]) : [];
  const grainText = grains.length > 0 ? grains.join(" / ") : "no grains declared";
  return `Charted by ${field}, viewable by ${grainText}`;
}

function summarizeWindows(time: Record<string, unknown>): string[] {
  const windows = Array.isArray(time.windows)
    ? (time.windows as Array<{ days?: number; step?: string }>)
    : [];
  return windows.map(
    (w) =>
      `Trailing ${w.days ?? "?"} days, computed ${
        w.step === "week" ? "weekly" : "daily"
      }`,
  );
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[140px_minmax(0,1fr)] sm:gap-4">
      <dt className="text-muted-foreground text-sm">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export function MetricDefinitionSummary({ doc }: { doc: Record<string, unknown> }) {
  const spec = (doc.spec ?? {}) as Record<string, unknown>;
  const measure = (spec.measure ?? {}) as Record<string, unknown>;
  const time = (spec.time ?? {}) as Record<string, unknown>;
  const display = (spec.display ?? {}) as Record<string, unknown>;
  const entity = String(spec.entity ?? "");
  const dimensions = Array.isArray(spec.dimensions)
    ? (spec.dimensions as string[])
    : [];
  const windows = summarizeWindows(time);
  const extendsParent =
    typeof spec.extends === "string" && spec.extends ? String(spec.extends) : null;

  return (
    <dl
      className="border-border space-y-3 rounded-lg border p-4"
      data-testid="metric-definition-summary"
    >
      {extendsParent && (
        <Row label="Variant of">
          <span className="font-mono">{extendsParent}</span>
        </Row>
      )}
      <Row label="Measures">
        {entity || measure.type
          ? summarizeMeasure(measure, entity || "record")
          : "Not defined yet"}
      </Row>
      <Row label="Filters">{summarizeFilters(spec.filters)}</Row>
      <Row label="Time">
        <div className="space-y-1">
          <div>{summarizeTime(time)}</div>
          {windows.map((w) => (
            <div key={w} className="text-muted-foreground">
              {w}
            </div>
          ))}
        </div>
      </Row>
      <Row label="Breakdowns">
        {dimensions.length === 0 ? (
          "None"
        ) : (
          <span className="flex flex-wrap gap-1.5">
            {dimensions.map((d) => (
              <span
                key={d}
                className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 font-mono text-xs"
              >
                {d}
              </span>
            ))}
          </span>
        )}
      </Row>
      <Row label="Display">
        {[
          display.unit ? `unit: ${String(display.unit)}` : null,
          display.format ? `format: ${String(display.format)}` : null,
          display.direction ? String(display.direction).replace(/_/g, " ") : null,
        ]
          .filter(Boolean)
          .join(" · ") || "Defaults"}
      </Row>
      <Row label="Visibility">
        {spec.visibility ? (
          <VisibilityBadge visibility={String(spec.visibility)} />
        ) : (
          "Not set"
        )}
      </Row>
    </dl>
  );
}
