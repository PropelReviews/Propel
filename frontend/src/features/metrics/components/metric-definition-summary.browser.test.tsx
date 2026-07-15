import { afterEach, describe, expect, it } from "vitest";

import { MetricDefinitionSummary } from "@/features/metrics/components/metric-definition-summary";
import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("MetricDefinitionSummary", () => {
  it("renders a plain-language summary of a metric document", async () => {
    result = renderInDom(
      <MetricDefinitionSummary
        doc={{
          apiVersion: "propel/v1",
          kind: "Metric",
          metadata: { id: "acme.cycle_time", name: "PR cycle time" },
          spec: {
            entity: "pull_request",
            measure: {
              type: "interval",
              from: "opened_at",
              to: "merged_at",
              agg: "median",
            },
            filters: [{ field: "merged_at", op: "is_not_null" }],
            time: {
              field: "merged_at",
              grains: ["day", "week"],
              windows: [{ days: 30, step: "day" }],
            },
            dimensions: ["repo"],
            display: {
              unit: "duration",
              format: "humanize_duration",
              direction: "lower_is_better",
            },
            visibility: "ic",
          },
        }}
      />,
    );

    await waitFor(() =>
      Boolean(
        result?.container.querySelector('[data-testid="metric-definition-summary"]'),
      ),
    );
    const text = result!.container.textContent!;
    expect(text).toContain("Median time from opened_at to merged_at per pull request");
    expect(text).toContain("merged_at is not null");
    expect(text).toContain("Charted by merged_at, viewable by day / week");
    expect(text).toContain("Trailing 30 days, computed daily");
    expect(text).toContain("repo");
    expect(text).toContain("lower is better");
  });

  it("summarizes counts and empty filters", async () => {
    result = renderInDom(
      <MetricDefinitionSummary
        doc={{
          spec: {
            entity: "release",
            measure: { type: "count" },
            filters: [],
            time: { field: "published_at", grains: ["week"] },
            visibility: "org",
          },
        }}
      />,
    );

    await waitFor(() =>
      Boolean(
        result?.container.querySelector('[data-testid="metric-definition-summary"]'),
      ),
    );
    const text = result!.container.textContent!;
    expect(text).toContain("Count of releases");
    expect(text).toContain("No filters");
    expect(text).toContain("Charted by published_at, viewable by week");
  });
});
