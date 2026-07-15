import { useMemo, useReducer, useState } from "react";

import {
  formatCount,
  formatDuration,
  formatPercent,
  formatWeekLabel,
  PropelLineChart,
  type TimeSeriesPoint,
  type ValueFormatter,
} from "@/components/charts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { MetricCatalogResponse } from "@/features/metrics/api/metric-definitions";
import {
  COMBINE_TEMPLATE_ID,
  METRIC_TEMPLATES,
  matchTemplate,
  type MetricTemplate,
} from "@/features/metrics/builder/metric-templates";
import {
  createDocumentState,
  documentReducer,
  emptyMetricDocument,
} from "@/features/metrics/document/store";
import { documentToYaml } from "@/features/metrics/document/yaml-io";
import { CodeBlock } from "@/components/ui/code-block";
import { cn } from "@/lib/utils";

const GRAINS = ["day", "week", "month", "quarter"] as const;

/** Catalog fixture so every shipped template is selectable without an API. */
export const DEMO_METRIC_CATALOG: MetricCatalogResponse = {
  catalog_version: 1,
  cardinality: { warn_above: 500, error_above: 5000 },
  entities: [
    {
      name: "pull_request",
      grain: "one row per PR",
      dbt_model: "pull_request",
      fields: [
        {
          name: "state",
          type: "enum",
          role: "dimension",
          values: ["open", "merged", "closed"],
          nullable: null,
          cardinality_estimate: 3,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "opened_at",
          type: "timestamp",
          role: "event_time",
          values: null,
          nullable: true,
          cardinality_estimate: null,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "merged_at",
          type: "timestamp",
          role: "event_time",
          values: null,
          nullable: true,
          cardinality_estimate: null,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "first_review_at",
          type: "timestamp",
          role: "event_time",
          values: null,
          nullable: true,
          cardinality_estimate: null,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "repo",
          type: "string",
          role: "dimension",
          values: null,
          nullable: null,
          cardinality_estimate: 200,
          person: false,
          virtual: false,
          mapping_id: null,
        },
      ],
    },
    {
      name: "review",
      grain: "one row per review",
      dbt_model: "review",
      fields: [
        {
          name: "submitted_at",
          type: "timestamp",
          role: "event_time",
          values: null,
          nullable: true,
          cardinality_estimate: null,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "state",
          type: "enum",
          role: "dimension",
          values: ["approved", "changes_requested", "commented"],
          nullable: null,
          cardinality_estimate: 3,
          person: false,
          virtual: false,
          mapping_id: null,
        },
      ],
    },
    {
      name: "release",
      grain: "one row per release",
      dbt_model: "release",
      fields: [
        {
          name: "published_at",
          type: "timestamp",
          role: "event_time",
          values: null,
          nullable: true,
          cardinality_estimate: null,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "is_draft",
          type: "boolean",
          role: "dimension",
          values: null,
          nullable: null,
          cardinality_estimate: 2,
          person: false,
          virtual: false,
          mapping_id: null,
        },
        {
          name: "is_prerelease",
          type: "boolean",
          role: "dimension",
          values: null,
          nullable: null,
          cardinality_estimate: 2,
          person: false,
          virtual: false,
          mapping_id: null,
        },
      ],
    },
  ],
  virtual_dimensions: [],
};

/** Deterministic 0–1 noise so the preview is stable across renders. */
function pseudoRandom(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

const DAY_MS = 24 * 60 * 60 * 1000;

const GRAIN_CONFIG: Record<string, { buckets: number; stepDays: number }> = {
  day: { buckets: 30, stepDays: 1 },
  week: { buckets: 12, stepDays: 7 },
  month: { buckets: 12, stepDays: 30 },
  quarter: { buckets: 8, stepDays: 91 },
};

/**
 * Fake but plausible preview series derived from the current document. The
 * seed folds in the entity/measure/filters so switching templates visibly
 * changes the chart, and the trend follows `display.direction`.
 */
function buildPreviewSeries(spec: Record<string, unknown>): TimeSeriesPoint[] {
  const measure = (spec.measure ?? {}) as Record<string, unknown>;
  const display = (spec.display ?? {}) as Record<string, unknown>;
  const time = (spec.time ?? {}) as Record<string, unknown>;
  const grains = Array.isArray(time.grains) ? (time.grains as string[]) : [];
  const grain = GRAINS.find((g) => grains.includes(g)) ?? "week";
  const { buckets, stepDays } = GRAIN_CONFIG[grain] ?? GRAIN_CONFIG.week;

  const unit = String(display.unit ?? "count");
  const direction = String(display.direction ?? "neutral");
  const base = unit === "duration" ? 28 : unit === "percent" ? 88 : 46;
  const trend =
    direction === "lower_is_better"
      ? -0.4
      : direction === "higher_is_better"
        ? 0.5
        : 0.05;
  const amplitude = base * 0.12;
  const seed = hashString(
    [
      String(spec.entity ?? ""),
      String(measure.type ?? ""),
      String(time.field ?? ""),
      JSON.stringify(spec.filters ?? []),
    ].join("|"),
  );

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const points: TimeSeriesPoint[] = [];
  for (let i = buckets - 1; i >= 0; i--) {
    const progress = (buckets - 1 - i) / buckets;
    const seasonal = Math.sin((buckets - i) / 2.1) * amplitude * 0.6;
    const noise = (pseudoRandom(seed + i) - 0.5) * amplitude;
    const raw = base * (1 + trend * progress) + seasonal + noise;
    const value = Math.max(0, Number(raw.toFixed(unit === "duration" ? 1 : 0)));
    const date = new Date(today.getTime() - i * stepDays * DAY_MS);
    points.push({ date: date.toISOString().slice(0, 10), value });
  }
  return points;
}

function previewFormatter(spec: Record<string, unknown>): ValueFormatter {
  const display = (spec.display ?? {}) as Record<string, unknown>;
  const format = String(display.format ?? "integer");
  if (format === "humanize_duration") return formatDuration;
  if (format.startsWith("percent")) return formatPercent;
  return formatCount;
}

function slugifyMetricName(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^[_0-9]+/, "")
    .replace(/_+$/, "")
    .slice(0, 63);
  return /^[a-z][a-z0-9_]{1,62}$/.test(slug) ? slug : "new_metric";
}

function KindCard({
  title,
  body,
  active,
  onClick,
}: {
  title: string;
  body: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={
        active
          ? "border-primary bg-primary/5 rounded-lg border p-3 text-left"
          : "border-border hover:bg-muted/40 rounded-lg border p-3 text-left"
      }
      onClick={onClick}
    >
      <div className="font-medium">{title}</div>
      <div className="text-muted-foreground mt-1 text-xs">{body}</div>
    </button>
  );
}

/**
 * Interactive create-metric form — same templates, numbered sections, and
 * document store as MetricBuilderPage — for the marketing landing (no auth/API).
 * "Save & publish" sends visitors to the live builder on app.*.
 */
export function MetricBuilderDemo({
  variant = "full",
  className,
  initialTemplateId = "review_latency",
}: {
  variant?: "hero" | "full";
  className?: string;
  /** Core template to preselect so the embed looks mid-creation. */
  initialTemplateId?: string;
}) {
  const isHero = variant === "hero";
  const catalog = DEMO_METRIC_CATALOG;
  const idNamespace = "demo";

  const [state, dispatch] = useReducer(documentReducer, undefined, () => {
    const base = createDocumentState(emptyMetricDocument(`${idNamespace}.new_metric`));
    const template = METRIC_TEMPLATES.find((t) => t.id === initialTemplateId);
    if (!template) return base;
    return {
      ...base,
      doc: {
        ...base.doc,
        metadata: {
          ...((base.doc.metadata as object) ?? {}),
          name: template.defaultName,
          description: template.description,
          id: `${idNamespace}.${slugifyMetricName(template.defaultName)}`,
        },
        spec: {
          ...((base.doc.spec as object) ?? {}),
          entity: template.spec.entity,
          measure: structuredClone(template.spec.measure),
          filters: structuredClone(template.spec.filters),
          time: structuredClone(template.spec.time),
          display: structuredClone(template.spec.display),
          visibility: "team",
        },
      },
    };
  });

  const [showYaml, setShowYaml] = useState(false);
  const doc = state.doc;
  const meta = (doc.metadata ?? {}) as Record<string, unknown>;
  const spec = useMemo(() => (doc.spec ?? {}) as Record<string, unknown>, [doc.spec]);
  const time = (spec.time ?? {}) as Record<string, unknown>;
  const grains = Array.isArray(time.grains) ? (time.grains as string[]) : [];
  const entity = String(spec.entity ?? "pull_request");
  const entities = catalog.entities;
  const entityMeta = entities.find((e) => e.name === entity);
  const eventTimeFields = (entityMeta?.fields ?? []).filter(
    (f) => f.role === "event_time",
  );
  const activeTemplateId = matchTemplate(spec);
  const yaml = useMemo(() => documentToYaml(doc), [doc]);
  const previewData = useMemo(() => buildPreviewSeries(spec), [spec]);
  const previewSeries = useMemo(
    () => [{ key: "value", label: String(meta.name ?? "Value") }],
    [meta.name],
  );
  const previewValueFormatter = useMemo(() => previewFormatter(spec), [spec]);

  const setMeta = (key: string, value: unknown) =>
    dispatch({ type: "patch", patch: { op: "set", path: ["metadata", key], value } });
  const setSpec = (key: string, value: unknown) =>
    dispatch({ type: "patch", patch: { op: "set", path: ["spec", key], value } });

  const onNameChange = (name: string) => {
    dispatch({
      type: "patch",
      patch: {
        op: "set",
        path: [],
        value: {
          ...doc,
          metadata: {
            ...meta,
            name,
            id: `${idNamespace}.${slugifyMetricName(name)}`,
          },
        },
      },
    });
  };

  function applyTemplate(template: MetricTemplate) {
    const currentName = String(meta.name ?? "");
    const currentDesc = String(meta.description ?? "");
    const nameIsDefault =
      currentName === "" ||
      currentName === "New metric" ||
      METRIC_TEMPLATES.some((t) => t.defaultName === currentName);
    const descIsDefault =
      currentDesc === "" || METRIC_TEMPLATES.some((t) => t.description === currentDesc);
    const nextName = nameIsDefault ? template.defaultName : currentName;
    dispatch({
      type: "patch",
      patch: {
        op: "set",
        path: [],
        value: {
          ...doc,
          metadata: {
            ...meta,
            ...(nameIsDefault ? { name: template.defaultName } : {}),
            ...(descIsDefault ? { description: template.description } : {}),
            id: `${idNamespace}.${slugifyMetricName(nextName)}`,
          },
          spec: {
            ...spec,
            entity: template.spec.entity,
            measure: structuredClone(template.spec.measure),
            filters: structuredClone(template.spec.filters),
            time: structuredClone(template.spec.time),
            display: structuredClone(template.spec.display),
          },
        },
      },
    });
  }

  // The demo can't persist anything — "Save & publish" hands off to the
  // closing CTA where visitors pick GitHub or Propel Cloud.
  const publishHref = "#get-started";

  return (
    <div
      data-slot="metric-builder-demo"
      data-variant={variant}
      className={cn(
        "border-border/60 bg-card overflow-hidden rounded-xl border shadow-sm",
        className,
      )}
    >
      <div className="border-border/60 flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3 sm:px-5">
        <div>
          <div className="text-sm font-medium">New metric</div>
          <p className="text-muted-foreground text-xs">
            Pick a core metric, adjust the basics — same builder as Propel Cloud.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            type="button"
            onClick={() => dispatch({ type: "undo" })}
          >
            Undo
          </Button>
          <Button
            size="sm"
            variant="outline"
            type="button"
            onClick={() => setShowYaml((v) => !v)}
          >
            {showYaml ? "Form mode" : "View as YAML"}
          </Button>
          <Button size="sm" asChild>
            <a href={publishHref}>Save &amp; publish</a>
          </Button>
        </div>
      </div>

      <div
        className={cn(
          "grid gap-6 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_300px]",
          isHero ? "max-h-[28rem] overflow-y-auto" : "max-h-[40rem] overflow-y-auto",
        )}
      >
        <div className="min-w-0 space-y-8">
          {showYaml ? (
            <CodeBlock code={yaml} className="text-xs" />
          ) : (
            <>
              <section className="space-y-3">
                <h2 className="text-lg font-medium">① Choose a core metric</h2>
                <p className="text-muted-foreground text-sm">
                  Start from a proven metric — everything can be fine-tuned below.
                </p>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {METRIC_TEMPLATES.map((template) => (
                    <KindCard
                      key={template.id}
                      title={template.title}
                      body={template.description}
                      active={activeTemplateId === template.id}
                      onClick={() => applyTemplate(template)}
                    />
                  ))}
                  <KindCard
                    title="Combine metrics"
                    body="Ratio or formula over existing metrics."
                    active={activeTemplateId === COMBINE_TEMPLATE_ID}
                    onClick={() =>
                      setSpec("measure", {
                        type: "ratio",
                        numerator: { ref: "" },
                        denominator: { ref: "" },
                        zero_denominator: null,
                      })
                    }
                  />
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">② Basics</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="demo-metric-name">Name</Label>
                    <Input
                      id="demo-metric-name"
                      value={String(meta.name ?? "")}
                      onChange={(e) => onNameChange(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label>Identifier</Label>
                    <p className="text-muted-foreground mt-2.5 font-mono text-sm">
                      {String(meta.id ?? "")
                        .split(".")
                        .slice(1)
                        .join(".") || String(meta.id ?? "")}
                    </p>
                  </div>
                </div>
                <div>
                  <Label htmlFor="demo-metric-desc">Description</Label>
                  <textarea
                    id="demo-metric-desc"
                    className="border-input bg-background mt-1 min-h-20 w-full rounded-lg border p-2 text-sm"
                    value={String(meta.description ?? "")}
                    onChange={(e) => setMeta("description", e.target.value)}
                  />
                </div>
              </section>

              <section className="space-y-4">
                <h2 className="text-lg font-medium">③ Time</h2>
                <div className="space-y-1">
                  <Label>Date used on the chart</Label>
                  <Select
                    value={String(time.field ?? "")}
                    onValueChange={(field) => setSpec("time", { ...time, field })}
                  >
                    <SelectTrigger className="mt-1 w-56">
                      <SelectValue placeholder="Pick a date field" />
                    </SelectTrigger>
                    <SelectContent>
                      {eventTimeFields.map((f) => (
                        <SelectItem key={f.name} value={f.name}>
                          {f.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>Chart by</Label>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {GRAINS.map((g) => {
                      const checked = grains.includes(g);
                      return (
                        <button
                          key={g}
                          type="button"
                          aria-pressed={checked}
                          className={
                            checked
                              ? "border-primary bg-primary/5 text-foreground rounded-full border px-3 py-1 text-sm"
                              : "border-border text-muted-foreground hover:bg-muted/40 rounded-full border px-3 py-1 text-sm"
                          }
                          onClick={() => {
                            const next = checked
                              ? grains.filter((x) => x !== g)
                              : [...grains, g];
                            setSpec("time", { ...time, grains: next });
                          }}
                        >
                          {g.charAt(0).toUpperCase() + g.slice(1)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </section>

              <section className="space-y-3">
                <h2 className="text-lg font-medium">④ Visibility</h2>
                <div className="grid gap-3 sm:grid-cols-3">
                  {(
                    [
                      ["ic", "IC", "Surfaced to each individual about their own work."],
                      ["team", "Team", "Visible to the team."],
                      ["org", "Org", "Visible across the organization."],
                    ] as const
                  ).map(([value, title, copy]) => (
                    <button
                      key={value}
                      type="button"
                      className={
                        spec.visibility === value
                          ? "border-primary bg-primary/5 rounded-lg border p-3 text-left"
                          : "border-border hover:bg-muted/40 rounded-lg border p-3 text-left"
                      }
                      onClick={() => setSpec("visibility", value)}
                    >
                      <div className="font-medium">{title}</div>
                      <div className="text-muted-foreground mt-1 text-xs">{copy}</div>
                    </button>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>

        <aside
          data-testid="demo-preview-panel"
          className="border-border bg-muted/20 h-fit space-y-3 rounded-lg border p-4 lg:sticky lg:top-0"
        >
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-medium">Preview</h2>
            <span className="text-muted-foreground text-xs">Sample data</span>
          </div>
          <PropelLineChart
            data={previewData}
            series={previewSeries}
            height={160}
            xFormatter={formatWeekLabel}
            valueFormatter={previewValueFormatter}
            emptyMessage="No chartable points"
          />
          <p className="text-muted-foreground text-xs">
            {String(meta.name ?? "New metric")} · updates as you edit
          </p>
        </aside>
      </div>
    </div>
  );
}
