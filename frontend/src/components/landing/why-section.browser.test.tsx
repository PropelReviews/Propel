import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { WhySection } from "./why-section";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("WhySection", () => {
  it("renders the imposed-metrics contrast and closing line", async () => {
    result = renderInDom(<WhySection />);
    const { container } = result;

    await waitFor(() =>
      container.textContent!.includes("Nobody wants imposed metrics"),
    );

    expect(container.textContent).toContain("Most tools");
    expect(container.textContent).toContain("Definitions you didn't choose");
    expect(container.textContent).toContain("Definitions your team writes");
    expect(container.textContent).toContain(
      "The only metrics people trust are the ones they chose.",
    );
  });
});
