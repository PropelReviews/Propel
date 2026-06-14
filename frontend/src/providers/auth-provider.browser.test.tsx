import { afterEach, describe, expect, it } from "vitest";

import { AuthProvider, useAuth } from "@/providers/auth-provider";
import {
  cleanupAuthAndFetch,
  mockApi,
  seedAuth,
  TEST_USER,
} from "@/test/access-test-utils";
import { renderInDom, waitFor, type RenderResult } from "@/test/render-browser";

function AuthProbe() {
  const { status, user } = useAuth();
  return <p>{`status:${status} email:${user?.email ?? "none"}`}</p>;
}

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

describe("AuthProvider", () => {
  it("bootstraps to authenticated when getMe succeeds", async () => {
    seedAuth();
    mockApi({});
    result = renderInDom(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() =>
      result!.container.textContent!.includes("status:authenticated"),
    );
    expect(result!.container.textContent).toContain(TEST_USER.email);
    expect(localStorage.getItem("propel_user")).toContain(TEST_USER.email);
  });

  it("bootstraps to anonymous and clears cache on 401", async () => {
    localStorage.setItem("propel_user", JSON.stringify(TEST_USER));
    mockApi({ user: null });
    result = renderInDom(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    );

    await waitFor(() => result!.container.textContent!.includes("status:anonymous"));
    expect(localStorage.getItem("propel_user")).toBeNull();
  });
});
