import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { HeroSection } from "./hero-section";
import { githubUrl } from "./links";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("HeroSection", () => {
  it("renders punchy headline, CTAs, and the interactive builder", async () => {
    result = renderInDom(<HeroSection />);
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Metrics your team"));

    expect(container.textContent).toContain("actually wants.");
    expect(container.textContent).toContain("Open source. Self-hostable.");

    const githubCta = container.querySelector<HTMLAnchorElement>(
      `a[href="${githubUrl}"]`,
    );
    expect(githubCta?.textContent).toContain("Star on GitHub");

    const defineCta = container.querySelector<HTMLAnchorElement>('a[href="#define"]');
    expect(defineCta?.textContent).toContain("Create a metric");

    const builder = container.querySelector(
      '[data-slot="metric-builder-demo"][data-variant="hero"]',
    );
    expect(builder).not.toBeNull();
    expect(builder!.textContent).toContain("Choose a core metric");
    expect(builder!.textContent).toContain("Time to first review");
  });
});
