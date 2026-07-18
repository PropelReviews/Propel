import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

const blogFlag = vi.fn(() => false);
const careersFlag = vi.fn(() => false);

vi.mock("@/hooks/use-landing-blog-flag", () => ({
  useLandingBlogFlag: () => blogFlag(),
  LANDING_BLOG_FEATURE_FLAG: "landing-blog",
}));

vi.mock("@/hooks/use-landing-careers-flag", () => ({
  useLandingCareersFlag: () => careersFlag(),
  LANDING_CAREERS_FEATURE_FLAG: "landing-careers",
}));

vi.mock("@/hooks/use-auth-flag", () => ({
  useAuthFlag: () => false,
  AUTH_FEATURE_FLAG: "signup-signin",
}));

vi.mock("posthog-js/react", () => ({
  usePostHog: () => null,
}));

import { LandingRoutes } from "./landing-routes";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
});

beforeEach(() => {
  blogFlag.mockReturnValue(false);
  careersFlag.mockReturnValue(false);
});

function renderAt(path: string) {
  result = renderInDom(
    <MemoryRouter initialEntries={[path]}>
      <LandingRoutes />
    </MemoryRouter>,
  );
  return result;
}

describe("LandingRoutes feature flags", () => {
  it("redirects /blog home when landing-blog is off", async () => {
    const { container } = renderAt("/blog");
    await waitFor(() => container.textContent!.includes("Metrics your team"));
    expect(container.textContent).not.toContain("Hello from Propel");
  });

  it("shows blog index when landing-blog is on", async () => {
    blogFlag.mockReturnValue(true);
    const { container } = renderAt("/blog");
    await waitFor(() => container.textContent!.includes("Hello from Propel"));
    expect(container.querySelector('a[href="/blog/hello-propel"]')).not.toBeNull();
  });

  it("redirects /careers home when landing-careers is off", async () => {
    const { container } = renderAt("/careers");
    await waitFor(() => container.textContent!.includes("Metrics your team"));
    expect(container.textContent).not.toContain("sam@propel.ninja");
  });

  it("shows careers page when landing-careers is on", async () => {
    careersFlag.mockReturnValue(true);
    const { container } = renderAt("/careers");
    await waitFor(() => container.textContent!.includes("sam@propel.ninja"));
    expect(container.querySelector('a[href="mailto:sam@propel.ninja"]')).not.toBeNull();
  });

  it("shows Blog and Careers nav links only when flags are on", async () => {
    blogFlag.mockReturnValue(true);
    careersFlag.mockReturnValue(true);
    const { container } = renderAt("/");
    await waitFor(() => container.textContent!.includes("Metrics your team"));

    const nav = container.querySelector("header nav");
    expect(nav?.textContent).toContain("Blog");
    expect(nav?.textContent).toContain("Careers");
    expect(container.querySelector('header a[href="/blog"]')).not.toBeNull();
    expect(container.querySelector('header a[href="/careers"]')).not.toBeNull();
  });

  it("hides Blog and Careers nav links when flags are off", async () => {
    const { container } = renderAt("/");
    await waitFor(() => container.textContent!.includes("Metrics your team"));

    expect(container.querySelector('header a[href="/blog"]')).toBeNull();
    expect(container.querySelector('header a[href="/careers"]')).toBeNull();
  });
});
