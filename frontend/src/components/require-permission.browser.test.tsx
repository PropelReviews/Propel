import { afterEach, describe, expect, it } from "vitest";

import {
  cleanupAuthAndFetch,
  makeTenant,
  mockApi,
  renderWithProviders,
  seedAuth,
} from "@/test/access-test-utils";
import { waitFor, type RenderResult } from "@/test/render-browser";

import { RequirePermission } from "./require-permission";

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

describe("RequirePermission", () => {
  it("renders children when the tenant grants one of the permissions", async () => {
    seedAuth();
    mockApi({ tenants: [makeTenant({ permissions: ["roles:manage"] })] });

    result = renderWithProviders(
      <RequirePermission anyOf={["roles:manage", "members:assign_role"]}>
        <p>Secret settings</p>
      </RequirePermission>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Secret settings"));
    expect(container.textContent).not.toContain("Access denied");
  });

  it("shows the access denied card when the permission is missing", async () => {
    seedAuth();
    mockApi({
      tenants: [makeTenant({ role: "member", permissions: ["metrics:read"] })],
    });

    result = renderWithProviders(
      <RequirePermission anyOf={["roles:manage"]}>
        <p>Secret settings</p>
      </RequirePermission>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Access denied"));
    expect(container.textContent).toContain(
      "You don't have permission to view this page",
    );
    expect(container.textContent).not.toContain("Secret settings");
  });

  it("explains when the user has no workspace at all", async () => {
    seedAuth();
    mockApi({ tenants: [] });

    result = renderWithProviders(
      <RequirePermission anyOf={["roles:manage"]}>
        <p>Secret settings</p>
      </RequirePermission>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Access denied"));
    expect(container.textContent).toContain("You don't belong to a workspace yet.");
    expect(container.textContent).not.toContain("Secret settings");
  });

  it("shows a loading state while tenants are still loading", async () => {
    seedAuth();
    // The tenant list request never resolves, pinning status at "loading".
    mockApi({ hang: /^\/api\/v1\/tenants\/$/ });

    result = renderWithProviders(
      <RequirePermission anyOf={["roles:manage"]}>
        <p>Secret settings</p>
      </RequirePermission>,
    );
    const { container } = result;

    await waitFor(() => container.textContent!.includes("Loading…"));
    expect(container.textContent).not.toContain("Secret settings");
    expect(container.textContent).not.toContain("Access denied");
  });
});
