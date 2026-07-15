import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { DifferentiatorsSection } from "./differentiators-section";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("DifferentiatorsSection", () => {
  it("renders verify cards and the four-step trace sequence", async () => {
    result = renderInDom(<DifferentiatorsSection />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Don't trust it. Verify it."));

    expect(container.querySelector("#transparency")).not.toBeNull();
    expect(container.textContent).toContain("Open source core");
    expect(container.textContent).toContain("Changeable");
    expect(container.textContent).toContain("Click to trace");
    expect(container.textContent).toContain("Cycle time: 2.4 days");
    expect(container.textContent).toContain("pr#1842 opened → reviewed → merged");

    const codeBlocks = container.querySelectorAll('[data-slot="code-block"]');
    expect(codeBlocks.length).toBeGreaterThanOrEqual(2);
    expect(codeBlocks[0].textContent).toContain("metric: cycle_time");
    expect(codeBlocks[1].textContent).toContain("SELECT avg(merged_at - opened_at)");
  });
});
