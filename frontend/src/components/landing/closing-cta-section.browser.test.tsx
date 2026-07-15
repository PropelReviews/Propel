import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { ClosingCtaSection } from "./closing-cta-section";
import { githubUrl } from "./links";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("ClosingCtaSection", () => {
  it("renders the closing headline and GitHub CTA", async () => {
    result = renderInDom(<ClosingCtaSection />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Measure what you mean."));

    expect(container.textContent).toContain("Clone it. Run it. Read every line.");

    const githubCta = container.querySelector<HTMLAnchorElement>(
      `a[href="${githubUrl}"]`,
    );
    expect(githubCta?.textContent).toContain("Get started on GitHub");

    expect(container.textContent).not.toContain("someone else's yardstick");
  });
});
