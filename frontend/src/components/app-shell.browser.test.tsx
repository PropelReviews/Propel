import { afterEach, describe, expect, it } from "vitest";

import { useTenant } from "@/providers/tenant-provider";
import {
  cleanupAuthAndFetch,
  makeTenant,
  mockApi,
  renderWithProviders,
  seedAuth,
} from "@/test/access-test-utils";
import { waitFor, type RenderResult } from "@/test/render-browser";

import { AppShell } from "./app-shell";

import type { Tenant } from "@/lib/tenants";

/** Exposes the tenant load status so tests can wait for it deterministically. */
function TenantStatusProbe() {
  const { status } = useTenant();
  return <span data-testid="tenant-status">{status}</span>;
}

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

async function mountShell(tenants: Tenant[]): Promise<HTMLElement> {
  seedAuth();
  mockApi({ tenants });
  result = renderWithProviders(
    <AppShell>
      <TenantStatusProbe />
    </AppShell>,
  );
  const { container } = result;
  await waitFor(
    () =>
      container.querySelector('[data-testid="tenant-status"]')?.textContent === "ready",
  );
  return container;
}

describe("AppShell", () => {
  it("shows the Access nav link when the user has a management permission", async () => {
    const container = await mountShell([
      makeTenant({ permissions: ["members:assign_role"] }),
    ]);

    const link = container.querySelector('a[href="/settings/access"]');
    expect(link).not.toBeNull();
    expect(link!.textContent).toBe("Access");
  });

  it("shows the Access nav link with roles:manage", async () => {
    const container = await mountShell([makeTenant({ permissions: ["roles:manage"] })]);

    expect(container.querySelector('a[href="/settings/access"]')).not.toBeNull();
  });

  it("hides the Access nav link without management permissions", async () => {
    const container = await mountShell([
      makeTenant({ role: "individual", permissions: ["metrics:read", "tenant:read"] }),
    ]);

    // The rest of the nav renders for authenticated users.
    expect(container.querySelector('a[href="/data"]')).not.toBeNull();
    expect(container.querySelector('a[href="/metrics"]')).not.toBeNull();
    expect(container.querySelector('a[href="/settings/access"]')).toBeNull();
  });

  it("renders the workspace switcher when the user has multiple tenants", async () => {
    const container = await mountShell([
      makeTenant({ id: "tenant-1", name: "Acme", slug: "acme" }),
      makeTenant({ id: "tenant-2", name: "Globex", slug: "globex" }),
    ]);

    const trigger = container.querySelector(
      '[data-slot="select-trigger"][aria-label="Switch workspace"]',
    );
    expect(trigger).not.toBeNull();
    // Selection defaults to the first tenant.
    expect(trigger!.textContent).toContain("Acme");
  });

  it("omits the workspace switcher with a single tenant", async () => {
    const container = await mountShell([makeTenant()]);

    expect(container.querySelector('[aria-label="Switch workspace"]')).toBeNull();
    // Sign out is still available.
    const signOut = [...container.querySelectorAll("button")].find(
      (b) => b.textContent === "Sign out",
    );
    expect(signOut).not.toBeUndefined();
  });
});
