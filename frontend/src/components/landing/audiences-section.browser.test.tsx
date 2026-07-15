import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { AudiencesSection } from "./audiences-section";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("AudiencesSection", () => {
  it("renders developer and leader benefit copy", async () => {
    result = renderInDom(<AudiencesSection />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Built for developers first"));

    expect(container.textContent).toContain("Metrics you can change");
    expect(container.textContent).toContain("Your record is yours.");
    expect(container.textContent).toContain("Same numbers. No hidden scorecard.");
    expect(container.textContent).toContain("Measure your strategy");
    expect(container.textContent).toContain("Unblock, don't surveil");
    expect(container.textContent).toContain(
      "Metrics leaders need. Metrics developers want. Only in the open.",
    );
  });
});
