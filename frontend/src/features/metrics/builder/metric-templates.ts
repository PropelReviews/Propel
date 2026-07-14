/**
 * Curated "core metric" presets for the builder.
 * Specs mirror the standard propel.* configs so a template click produces a
 * document that matches what the platform already computes well.
 */

export type MetricTemplateSpec = {
  entity: string;
  measure: Record<string, unknown>;
  filters: unknown[];
  time: { field: string; grains: string[] };
  display: { unit: string; format: string; direction: string };
};

export type MetricTemplate = {
  id: string;
  title: string;
  description: string;
  /** Suggested metadata.name when the doc is still untouched. */
  defaultName: string;
  spec: MetricTemplateSpec;
};

export const COMBINE_TEMPLATE_ID = "combine";

export const METRIC_TEMPLATES: MetricTemplate[] = [
  {
    id: "merged_prs",
    title: "Merged pull requests",
    description: "How many PRs your team merges over time.",
    defaultName: "Merged pull requests",
    spec: {
      entity: "pull_request",
      measure: { type: "count" },
      filters: [{ field: "merged_at", op: "is_not_null" }],
      time: { field: "merged_at", grains: ["day", "week", "month"] },
      display: { unit: "count", format: "integer", direction: "neutral" },
    },
  },
  {
    id: "cycle_time",
    title: "PR cycle time",
    description: "Median time from PR open to merge.",
    defaultName: "PR cycle time",
    spec: {
      entity: "pull_request",
      measure: {
        type: "interval",
        from: "opened_at",
        to: "merged_at",
        agg: "median",
        null_handling: "exclude",
        negative_handling: "exclude",
      },
      filters: [{ field: "merged_at", op: "is_not_null" }],
      time: { field: "merged_at", grains: ["day", "week", "month"] },
      display: {
        unit: "duration",
        format: "humanize_duration",
        direction: "lower_is_better",
      },
    },
  },
  {
    id: "review_latency",
    title: "Time to first review",
    description: "Median wait from PR open to the first review.",
    defaultName: "Time to first review",
    spec: {
      entity: "pull_request",
      measure: {
        type: "interval",
        from: "opened_at",
        to: "first_review_at",
        agg: "median",
        null_handling: "exclude",
        negative_handling: "exclude",
      },
      filters: [{ field: "first_review_at", op: "is_not_null" }],
      time: { field: "first_review_at", grains: ["day", "week", "month"] },
      display: {
        unit: "duration",
        format: "humanize_duration",
        direction: "lower_is_better",
      },
    },
  },
  {
    id: "reviews_submitted",
    title: "Reviews submitted",
    description: "How many PR reviews get submitted over time.",
    defaultName: "Reviews submitted",
    spec: {
      entity: "review",
      measure: { type: "count" },
      filters: [],
      time: { field: "submitted_at", grains: ["day", "week", "month"] },
      display: { unit: "count", format: "integer", direction: "neutral" },
    },
  },
  {
    id: "releases_published",
    title: "Releases published",
    description: "Published, non-draft releases — a deploy-frequency proxy.",
    defaultName: "Releases published",
    spec: {
      entity: "release",
      measure: { type: "count" },
      filters: [
        { field: "is_draft", op: "eq", value: false },
        { field: "is_prerelease", op: "eq", value: false },
        { field: "published_at", op: "is_not_null" },
      ],
      time: { field: "published_at", grains: ["day", "week", "month"] },
      display: { unit: "count", format: "integer", direction: "higher_is_better" },
    },
  },
];

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    const entries = Object.keys(value as object)
      .sort()
      .map((k) => `${k}:${canonical((value as Record<string, unknown>)[k])}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

/**
 * Which template the current document matches, if any.
 * Returns COMBINE_TEMPLATE_ID for ratio/formula measures and null for
 * anything hand-tuned beyond a template ("custom").
 */
export function matchTemplate(spec: Record<string, unknown>): string | null {
  const measureType = ((spec.measure ?? {}) as Record<string, unknown>).type;
  if (measureType === "ratio" || measureType === "formula") {
    return COMBINE_TEMPLATE_ID;
  }
  for (const template of METRIC_TEMPLATES) {
    const matches =
      spec.entity === template.spec.entity &&
      canonical(spec.measure ?? {}) === canonical(template.spec.measure) &&
      canonical(spec.filters ?? []) === canonical(template.spec.filters) &&
      canonical(spec.time ?? {}) === canonical(template.spec.time);
    if (matches) return template.id;
  }
  return null;
}
