import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

// No jsdom/happy-dom env is configured, so we render to a static HTML string
// (works in the default node environment) and assert on the emitted markup.
// This keeps the test lightweight while still verifying the real component
// output rather than reconstructing the attribute strings by hand.

describe("Button autocapture attributes", () => {
  it("emits data-ph-capture-attribute-* from props", () => {
    const html = renderToStaticMarkup(
      <Button variant="outline" size="sm" analyticsName="get_started">
        Get Started
      </Button>,
    );

    expect(html).toContain('data-ph-capture-attribute-component="button"');
    expect(html).toContain('data-ph-capture-attribute-variant="outline"');
    expect(html).toContain('data-ph-capture-attribute-size="sm"');
    expect(html).toContain('data-ph-capture-attribute-name="get_started"');
  });

  it("falls back to default variant/size and omits name when unset", () => {
    const html = renderToStaticMarkup(<Button>Click</Button>);

    expect(html).toContain('data-ph-capture-attribute-component="button"');
    expect(html).toContain('data-ph-capture-attribute-variant="default"');
    expect(html).toContain('data-ph-capture-attribute-size="default"');
    expect(html).not.toContain("data-ph-capture-attribute-name");
  });
});
