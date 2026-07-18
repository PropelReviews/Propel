import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { MarketingLayout } from "./marketing-layout";

vi.mock("@/hooks/use-landing-blog-flag", () => ({
  useLandingBlogFlag: () => true,
  LANDING_BLOG_FEATURE_FLAG: "landing-blog",
}));

vi.mock("@/hooks/use-landing-careers-flag", () => ({
  useLandingCareersFlag: () => true,
  LANDING_CAREERS_FEATURE_FLAG: "landing-careers",
}));

vi.mock("@/hooks/use-auth-flag", () => ({
  useAuthFlag: () => false,
  AUTH_FEATURE_FLAG: "signup-signin",
}));

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

describe("MarketingLayout", () => {
  it("links the brand home and exposes flag-gated Blog/Careers links", async () => {
    result = renderInDom(
      <MemoryRouter>
        <MarketingLayout>
          <p>Page body</p>
        </MarketingLayout>
      </MemoryRouter>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Page body"));

    const brand = container.querySelector<HTMLAnchorElement>('header a[href="/"]');
    expect(brand?.textContent).toContain("Propel");

    expect(container.querySelector('header a[href="/blog"]')?.textContent).toBe("Blog");
    expect(container.querySelector('header a[href="/careers"]')?.textContent).toBe(
      "Careers",
    );

    expect(container.querySelector('footer a[href="/blog"]')).not.toBeNull();
    expect(container.querySelector('footer a[href="/careers"]')).not.toBeNull();
  });
});
