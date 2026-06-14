import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import type { AuthUser } from "@/lib/api";
import type { Invite } from "@/lib/invites";
import type { Member } from "@/lib/members";
import type { PermissionKey, Role } from "@/lib/permissions";
import type { PermissionDefinition, RolePermissions } from "@/lib/roles";
import type { Tenant } from "@/lib/tenants";
import { AuthProvider } from "@/providers/auth-provider";
import { TenantProvider } from "@/providers/tenant-provider";
import { renderInDom, type RenderResult } from "@/test/render-browser";

export const TEST_USER: AuthUser = {
  id: "user-self",
  email: "self@example.com",
  name: "Sam Self",
  is_active: true,
  email_verified: true,
  created_at: "2026-01-01T00:00:00Z",
};

export const ALL_PERMISSIONS: PermissionKey[] = [
  "tenant:read",
  "tenant:update",
  "tenant:delete",
  "members:read",
  "members:assign_role",
  "members:remove",
  "invites:read",
  "invites:revoke",
  "invites:role:owner",
  "invites:role:admin",
  "invites:role:manager",
  "invites:role:member",
  "connections:manage",
  "github_identities:manage",
  "ingestion:read",
  "metrics:read",
  "roles:manage",
];

export function makeTenant(overrides: Partial<Tenant> = {}): Tenant {
  return {
    id: "tenant-1",
    name: "Acme",
    slug: "acme",
    created_at: "2026-01-01T00:00:00Z",
    role: "admin",
    permissions: [],
    ...overrides,
  };
}

export function makeMember(
  overrides: Partial<Member> & Pick<Member, "user_id" | "email">,
): Member {
  return {
    name: null,
    role: "member",
    created_at: "2026-02-03T00:00:00Z",
    github_login: null,
    github_link_status: null,
    ...overrides,
  };
}

export type RecordedCall = {
  method: string;
  path: string;
  body?: unknown;
};

export type MockApiOptions = {
  /** When `null`, `/api/v1/auth/me` returns 401. Defaults to TEST_USER. */
  user?: AuthUser | null;
  tenants?: Tenant[];
  members?: Member[];
  invites?: Invite[];
  catalog?: PermissionDefinition[];
  rolePermissions?: RolePermissions[];
  /** Requests whose pathname matches never resolve (simulates loading). */
  hang?: RegExp;
};

/**
 * Stubs `globalThis.fetch` to serve the auth/tenant/access API surface from
 * in-memory fixtures. Returns the list of recorded calls (method + pathname +
 * parsed JSON body) for asserting outgoing requests.
 */
export function mockApi(options: MockApiOptions = {}): { calls: RecordedCall[] } {
  const {
    user: userOption,
    tenants = [],
    members = [],
    invites = [],
    catalog = [],
    rolePermissions = [],
    hang,
  } = options;
  const user = userOption === undefined ? TEST_USER : userOption;
  const calls: RecordedCall[] = [];

  const json = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  vi.stubGlobal(
    "fetch",
    (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const href =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.href
            : input.url;
      const path = new URL(href, "http://localhost:8000").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const body =
        typeof init?.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      calls.push({ method, path, body });

      if (hang?.test(path)) {
        return new Promise<Response>(() => {});
      }

      if (method === "GET" && path === "/api/v1/auth/me") {
        if (user === null) {
          return Promise.resolve(json({ detail: "Not authenticated" }, 401));
        }
        return Promise.resolve(json(user));
      }
      if (method === "GET" && path === "/api/v1/tenants/") {
        return Promise.resolve(json(tenants));
      }
      if (method === "GET" && /^\/api\/v1\/tenants\/[^/]+\/members\/$/.test(path)) {
        return Promise.resolve(json(members));
      }
      if (
        method === "PATCH" &&
        /^\/api\/v1\/tenants\/[^/]+\/members\/[^/]+\/role$/.test(path)
      ) {
        const userId = path.split("/")[6];
        const member = members.find((m) => m.user_id === userId);
        const { role } = body as { role: Role };
        return Promise.resolve(json({ ...member, role }));
      }
      if (
        method === "DELETE" &&
        /^\/api\/v1\/tenants\/[^/]+\/members\/[^/]+$/.test(path)
      ) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (method === "GET" && /^\/api\/v1\/tenants\/[^/]+\/invites$/.test(path)) {
        return Promise.resolve(json(invites));
      }
      if (method === "POST" && /^\/api\/v1\/tenants\/[^/]+\/invites$/.test(path)) {
        const { email, role } = body as { email: string; role: Role };
        const invite: Invite = {
          id: `invite-${calls.length}`,
          email,
          role,
          expires_at: "2026-07-01T00:00:00Z",
          created_at: "2026-06-09T00:00:00Z",
          invited_by_user_id: user.id,
        };
        return Promise.resolve(
          json({ invite, invite_url: `http://app.test/invite/${invite.id}` }, 201),
        );
      }
      if (
        method === "DELETE" &&
        /^\/api\/v1\/tenants\/[^/]+\/invites\/[^/]+$/.test(path)
      ) {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      if (method === "GET" && path === "/api/v1/permissions/catalog") {
        return Promise.resolve(json(catalog));
      }
      if (method === "GET" && /^\/api\/v1\/tenants\/[^/]+\/roles$/.test(path)) {
        return Promise.resolve(json(rolePermissions));
      }
      if (method === "PUT" && /^\/api\/v1\/tenants\/[^/]+\/roles\/[^/]+$/.test(path)) {
        const role = path.split("/").pop() as Role;
        const { permissions } = body as { permissions: PermissionKey[] };
        return Promise.resolve(json({ role, permissions }));
      }
      return Promise.resolve(json({ detail: "NOT_FOUND" }, 404));
    },
  );

  return { calls };
}

/** Caches user for faster AuthProvider bootstrap in browser tests. */
export function seedAuth() {
  localStorage.setItem("propel_user", JSON.stringify(TEST_USER));
}

/** Clears storage (token, cached user, tenant selection) and fetch stubs. */
export function cleanupAuthAndFetch() {
  vi.unstubAllGlobals();
  localStorage.clear();
}

/** Mounts `ui` under MemoryRouter + AuthProvider + TenantProvider. */
export function renderWithProviders(ui: ReactNode): RenderResult {
  return renderInDom(
    <MemoryRouter>
      <AuthProvider>
        <TenantProvider>{ui}</TenantProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}
