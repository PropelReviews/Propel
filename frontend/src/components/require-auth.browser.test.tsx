import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { AuthProvider } from "@/providers/auth-provider";
import { cleanupAuthAndFetch, mockApi, seedAuth } from "@/test/access-test-utils";
import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

import { RequireAuth } from "./require-auth";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

function mountAt(path: string): HTMLElement {
  result = renderInDom(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/signin" element={<p>Sign in page</p>} />
          <Route
            path="/private"
            element={
              <RequireAuth>
                <p>Private page</p>
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
  return result.container;
}

describe("RequireAuth", () => {
  it("redirects anonymous users to the sign-in page", async () => {
    mockApi({});
    const container = mountAt("/private");

    await waitFor(() => container.textContent!.includes("Sign in page"));
    expect(container.textContent).not.toContain("Private page");
  });

  it("renders children once the session is authenticated", async () => {
    seedAuth();
    mockApi({});
    const container = mountAt("/private");

    await waitFor(() => container.textContent!.includes("Private page"));
    expect(container.textContent).not.toContain("Sign in page");
  });
});
