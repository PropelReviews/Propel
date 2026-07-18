import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { BlogIndexPage } from "./BlogIndexPage";

vi.mock("@/hooks/use-landing-blog-flag", () => ({
  useLandingBlogFlag: () => true,
  LANDING_BLOG_FEATURE_FLAG: "landing-blog",
}));

vi.mock("@/hooks/use-landing-careers-flag", () => ({
  useLandingCareersFlag: () => false,
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

describe("BlogIndexPage", () => {
  it("lists seeded blog posts", async () => {
    result = renderInDom(
      <MemoryRouter>
        <BlogIndexPage />
      </MemoryRouter>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Hello from Propel"));

    expect(container.textContent).toContain("Measuring what matters");
    const helloLink = container.querySelector<HTMLAnchorElement>(
      'a[href="/blog/hello-propel"]',
    );
    expect(helloLink).not.toBeNull();
  });
});
