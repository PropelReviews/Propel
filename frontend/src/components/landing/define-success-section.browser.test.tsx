import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { DefineSuccessSection } from "./define-success-section";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("DefineSuccessSection", () => {
  it("renders the interactive builder and support cards", async () => {
    result = renderInDom(<DefineSuccessSection />);
    const { container } = result;

    await waitFor(() =>
      container.textContent!.includes("Wanted metrics are self-defined"),
    );

    // Beat 1 — the goals → metrics table and the argument.
    expect(container.textContent).toContain("This quarter's goal");
    expect(container.textContent).toContain("The metric you'd build");
    expect(container.textContent).toContain("Ship the platform migration");
    expect(container.textContent).toContain("Migration PRs merged per week");
    expect(container.textContent).toContain("Raise code quality");
    expect(container.textContent).toContain("Rework rate on shipped work");
    expect(container.textContent).toContain("Deeper reviews, not faster ones");
    expect(container.textContent).toContain("Substantive comments per merged PR");
    expect(container.textContent).toContain(
      "when your goals change, your metrics change with them",
    );

    // Beat 2 — the wizard under the speed claim.
    expect(container.textContent).toContain(
      "Build it in minutes. No query language required.",
    );

    const builder = container.querySelector(
      '[data-slot="metric-builder-demo"][data-variant="full"]',
    );
    expect(builder).not.toBeNull();
    expect(builder!.textContent).toContain("① Choose a core metric");
    expect(builder!.textContent).toContain("② Basics");
    expect(builder!.textContent).toContain("③ Time");
    expect(builder!.textContent).toContain("④ Visibility");
    expect(builder!.textContent).toContain("Merged pull requests");

    expect(container.textContent).toContain("Start with standards");
    expect(container.textContent).toContain("Rewrite anything");
    expect(container.textContent).toContain("Versioned like code");
  });

  it("previews the metric in a chart that updates with the wizard", async () => {
    result = renderInDom(<DefineSuccessSection />);
    const { container } = result;

    await waitFor(() =>
      container.textContent!.includes("Wanted metrics are self-defined"),
    );

    const preview = container.querySelector('[data-testid="demo-preview-panel"]');
    expect(preview).not.toBeNull();
    expect(preview!.textContent).toContain("Preview");
    expect(preview!.textContent).toContain("Sample data");

    await waitFor(() => preview!.querySelector("svg.recharts-surface") !== null);
    const before = preview!.querySelector("path.recharts-curve")?.getAttribute("d");
    expect(before).toBeTruthy();

    const mergedPrs = Array.from(container.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("Merged pull requests"),
    );
    expect(mergedPrs).toBeDefined();
    mergedPrs!.click();

    await waitFor(() => {
      const after = preview!.querySelector("path.recharts-curve")?.getAttribute("d");
      return after != null && after !== before;
    });
  });

  it("lets visitors switch core metric templates", async () => {
    result = renderInDom(<DefineSuccessSection />);
    const { container } = result;

    await waitFor(() =>
      container.textContent!.includes("Wanted metrics are self-defined"),
    );

    const cycleTime = Array.from(container.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("PR cycle time"),
    );
    expect(cycleTime).toBeDefined();
    cycleTime!.click();

    await waitFor(() => {
      const name = container.querySelector<HTMLInputElement>("#demo-metric-name");
      return name?.value === "PR cycle time";
    });
  });
});
