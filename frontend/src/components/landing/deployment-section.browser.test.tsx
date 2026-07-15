import { afterEach, describe, expect, it } from "vitest";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { DeploymentSection } from "./deployment-section";
import { githubUrl } from "./links";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("DeploymentSection", () => {
  it("renders cloud and self-hosted cards with the clone snippet", async () => {
    result = renderInDom(<DeploymentSection />);
    const { container } = result;

    await waitFor(() =>
      container.textContent!.includes("Same software, however you run it"),
    );

    expect(container.textContent).toContain("Propel Cloud");
    expect(container.textContent).toContain(
      "Managed. Same metrics, same SQL, same transparency. Zero ops.",
    );
    expect(container.textContent).toContain("Self-hosted");
    expect(container.textContent).toContain("Your data never leaves.");
    expect(container.textContent).toContain("No account required");
    expect(container.textContent).toContain("No keys phoning home");

    const codeBlock = container.querySelector('[data-slot="code-block"]');
    expect(codeBlock?.textContent).toContain(
      "git clone https://github.com/PropelReviews/Propel",
    );
    expect(codeBlock?.textContent).toContain("docker-compose up");

    const docsLink = container.querySelector<HTMLAnchorElement>(
      `a[href="${githubUrl}"]`,
    );
    expect(docsLink?.textContent).toContain("Read the docs");

    // Waitlist (auth flag off) should sit in the card footer pinned to the bottom.
    const cloudCard = Array.from(container.querySelectorAll('[data-slot="card"]')).find(
      (card) => card.textContent?.includes("Propel Cloud"),
    );
    expect(cloudCard).toBeDefined();
    const footer = cloudCard!.querySelector('[data-slot="card-footer"]');
    expect(footer?.className).toContain("mt-auto");
    expect(footer?.textContent).toMatch(/Join the waitlist|You're on the list/);
  });
});
