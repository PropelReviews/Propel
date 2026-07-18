import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { CareersPage } from "./CareersPage";

vi.mock("@/hooks/use-landing-blog-flag", () => ({
  useLandingBlogFlag: () => false,
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

describe("CareersPage", () => {
  it("renders outreach copy and mailto to sam@propel.ninja", async () => {
    result = renderInDom(
      <MemoryRouter>
        <CareersPage />
      </MemoryRouter>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Careers"));

    expect(container.textContent).toContain("sam@propel.ninja");
    const mailto = container.querySelector<HTMLAnchorElement>(
      'a[href="mailto:sam@propel.ninja"]',
    );
    expect(mailto).not.toBeNull();
    expect(mailto!.textContent).toContain("sam@propel.ninja");
  });
});
