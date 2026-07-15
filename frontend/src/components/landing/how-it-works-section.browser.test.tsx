import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { HowItWorksSection } from "./how-it-works-section";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("HowItWorksSection", () => {
  it("renders Connect. Compute. Inspect. and three steps", async () => {
    result = renderInDom(<HowItWorksSection />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Connect. Compute. Inspect."));

    expect(container.textContent).toContain("Connect");
    expect(container.textContent).toContain("Open connector model");
    expect(container.textContent).toContain("Compute");
    expect(container.textContent).toContain("Inspect");
  });
});
