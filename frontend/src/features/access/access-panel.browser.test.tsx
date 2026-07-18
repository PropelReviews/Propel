import { afterEach, describe, expect, it } from "vitest";
import { userEvent } from "vitest/browser";

import {
  cleanupAuthAndFetch,
  makeMember,
  makeTenant,
  mockApi,
  renderWithProviders,
  seedAuth,
  TEST_USER,
  type MockApiOptions,
} from "@/test/access-test-utils";
import { waitFor, type RenderResult } from "@/test/render-browser";

import { AccessPanel } from "./access-panel";

import type { Invite } from "@/lib/invites";
import type { PermissionKey } from "@/lib/permissions";
import type { PermissionDefinition, RolePermissions } from "@/lib/roles";

const selfAdmin = makeMember({
  user_id: TEST_USER.id,
  email: TEST_USER.email,
  name: "Sam Self",
  role: "admin",
  github_login: "sam-self",
});

const otherAdmin = makeMember({
  user_id: "user-2",
  email: "ada@example.com",
  name: "Ada Admin",
  role: "admin",
});

const manager = makeMember({
  user_id: "user-3",
  email: "max@example.com",
  name: "Max Manager",
  role: "manager",
});

const pendingInvite: Invite = {
  id: "invite-1",
  email: "pending@example.com",
  role: "individual",
  expires_at: "2026-07-01T00:00:00Z",
  created_at: "2026-06-01T00:00:00Z",
  invited_by_user_id: TEST_USER.id,
};

const CATALOG: PermissionDefinition[] = [
  {
    key: "tenant:update",
    label: "Update workspace",
    description: "Rename the workspace",
    group: "Workspace",
  },
  {
    key: "members:assign_role",
    label: "Assign roles",
    description: "Change member roles",
    group: "Members",
  },
  {
    key: "members:remove",
    label: "Remove members",
    description: "Remove members from the workspace",
    group: "Members",
  },
  {
    key: "invites:read",
    label: "View invites",
    description: "See pending invites",
    group: "Invites",
  },
];

const ROLE_PERMS: RolePermissions[] = [
  {
    role: "admin",
    permissions: [
      "tenant:update",
      "members:assign_role",
      "members:remove",
      "invites:read",
    ],
  },
  { role: "manager", permissions: ["invites:read"] },
  { role: "individual", permissions: [] },
];

let result: RenderResult | undefined;

afterEach(() => {
  result?.unmount();
  result = undefined;
  cleanupAuthAndFetch();
});

async function mountAccess(
  permissions: PermissionKey[],
  options: Omit<MockApiOptions, "tenants"> = {},
) {
  seedAuth();
  const { calls } = mockApi({ tenants: [makeTenant({ permissions })], ...options });
  result = renderWithProviders(<AccessPanel />);
  const { container } = result;
  await waitFor(() => container.textContent!.includes("Access"));
  return { container, calls };
}

function findRow(container: HTMLElement, text: string): HTMLTableRowElement {
  const row = [...container.querySelectorAll<HTMLTableRowElement>("tbody tr")].find(
    (tr) => tr.textContent!.includes(text),
  );
  if (!row) throw new Error(`No table row containing "${text}"`);
  return row;
}

function findButton(root: ParentNode, text: string): HTMLButtonElement | undefined {
  return [...root.querySelectorAll<HTMLButtonElement>("button")].find(
    (b) => b.textContent === text,
  );
}

async function openTab(container: HTMLElement, label: string) {
  const trigger = [
    ...container.querySelectorAll<HTMLButtonElement>('[data-slot="tabs-trigger"]'),
  ].find((t) => t.textContent === label);
  if (!trigger) throw new Error(`No tab trigger labeled "${label}"`);
  await userEvent.click(trigger);
}

describe("AccessPanel members tab", () => {
  it("renders member rows with name, email, and role", async () => {
    const { container } = await mountAccess(
      ["members:read", "members:assign_role", "members:remove"],
      { members: [selfAdmin, manager] },
    );

    await waitFor(() => container.textContent!.includes("Sam Self"));
    expect(container.textContent).toContain("2 members in this workspace.");
    expect(container.textContent).toContain("self@example.com");
    expect(container.textContent).toContain("(you)");
    expect(container.textContent).toContain("max@example.com");
    // GitHub login renders as a badge; members without one get a dash.
    expect(container.textContent).toContain("sam-self");
    expect(findRow(container, "Max Manager").textContent).toContain("—");
  });

  it("shows a locked role badge instead of a select for the last admin", async () => {
    const { container } = await mountAccess(
      ["members:read", "members:assign_role", "members:remove"],
      { members: [selfAdmin, manager] },
    );
    await waitFor(() => container.textContent!.includes("Sam Self"));

    // Sole admin: no role select, outline badge with the role label instead.
    const adminRow = findRow(container, "Sam Self");
    expect(adminRow.querySelector('[data-slot="select-trigger"]')).toBeNull();
    const badges = [...adminRow.querySelectorAll('[data-slot="badge"]')].map(
      (b) => b.textContent,
    );
    expect(badges).toContain("Admin");

    // Other members keep an editable role select.
    const managerRow = findRow(container, "Max Manager");
    const select = managerRow.querySelector('[data-slot="select-trigger"]');
    expect(select).not.toBeNull();
    expect(select!.textContent).toContain("Manager");
  });

  it("hides the remove button for yourself but not for others", async () => {
    const { container } = await mountAccess(
      ["members:read", "members:assign_role", "members:remove"],
      { members: [selfAdmin, otherAdmin] },
    );
    await waitFor(() => container.textContent!.includes("Ada Admin"));

    // Two admins, so neither is the last admin; self still can't remove self.
    expect(findButton(findRow(container, "Sam Self"), "Remove")).toBeUndefined();
    expect(findButton(findRow(container, "Ada Admin"), "Remove")).not.toBeUndefined();
  });

  it("removes a member after confirming in the dialog", async () => {
    const { container, calls } = await mountAccess(
      ["members:read", "members:assign_role", "members:remove"],
      { members: [selfAdmin, otherAdmin] },
    );
    await waitFor(() => container.textContent!.includes("Ada Admin"));

    await userEvent.click(findButton(findRow(container, "Ada Admin"), "Remove")!);
    await waitFor(
      () =>
        document.body
          .querySelector('[data-slot="dialog-content"]')
          ?.textContent?.includes("Remove member") ?? false,
    );

    const dialog = document.body.querySelector('[data-slot="dialog-content"]')!;
    expect(dialog.textContent).toContain("Remove Ada Admin from this workspace?");
    await userEvent.click(
      [...dialog.querySelectorAll<HTMLButtonElement>("button")].find(
        (b) => b.dataset.variant === "destructive",
      )!,
    );

    await waitFor(() =>
      calls.some(
        (c) =>
          c.method === "DELETE" && c.path === "/api/v1/tenants/tenant-1/members/user-2",
      ),
    );
    await waitFor(() => !container.textContent!.includes("Ada Admin"));
  });

  it("hides the remove column entirely without members:remove", async () => {
    const { container } = await mountAccess(["members:read", "members:assign_role"], {
      members: [selfAdmin, otherAdmin],
    });
    await waitFor(() => container.textContent!.includes("Ada Admin"));

    expect(findButton(container, "Remove")).toBeUndefined();
  });
});

describe("AccessPanel invites tab", () => {
  it("hides the invite form for users who can only read invites", async () => {
    const { container } = await mountAccess(["members:read", "invites:read"], {
      members: [selfAdmin],
      invites: [pendingInvite],
    });
    await openTab(container, "Invites");

    await waitFor(() => container.textContent!.includes("pending@example.com"));
    expect(container.textContent).not.toContain("Invite someone");
    // No invites:revoke, so no revoke action either.
    expect(findButton(container, "Revoke")).toBeUndefined();
  });

  it("limits role options to the roles the user may invite", async () => {
    const { container } = await mountAccess(
      [
        "members:read",
        "invites:read",
        "invites:revoke",
        "invites:role:manager",
        "invites:role:individual",
      ],
      { members: [selfAdmin], invites: [pendingInvite] },
    );
    await openTab(container, "Invites");
    await waitFor(() => container.textContent!.includes("Invite someone"));

    // Default role is Individual when invitable.
    const trigger = container.querySelector<HTMLButtonElement>(
      '[data-slot="select-trigger"]',
    )!;
    expect(trigger.textContent).toContain("Individual");

    await userEvent.click(trigger);
    await waitFor(
      () => document.body.querySelectorAll('[data-slot="select-item"]').length > 0,
    );
    const options = [
      ...document.body.querySelectorAll('[data-slot="select-item"]'),
    ].map((o) => o.textContent);
    expect(options).toEqual(["Manager", "Individual"]);
    await userEvent.keyboard("{Escape}");

    // The pending invites table renders with a revoke action.
    await waitFor(() => container.textContent!.includes("pending@example.com"));
    expect(findButton(container, "Revoke")).not.toBeUndefined();
  });

  it("sends an invite and surfaces the invite link", async () => {
    const { container, calls } = await mountAccess(
      ["members:read", "invites:read", "invites:role:individual"],
      { members: [selfAdmin], invites: [] },
    );
    await openTab(container, "Invites");
    await waitFor(() => container.textContent!.includes("Invite someone"));
    expect(container.textContent).toContain("No pending invites.");

    await userEvent.fill(
      container.querySelector<HTMLInputElement>("#invite-email")!,
      "teammate@example.com",
    );
    await userEvent.click(findButton(container, "Send invite")!);

    await waitFor(() => container.textContent!.includes("Copy link"));
    const post = calls.find(
      (c) => c.method === "POST" && c.path === "/api/v1/tenants/tenant-1/invites",
    );
    expect(post?.body).toEqual({ email: "teammate@example.com", role: "individual" });
    expect(container.querySelector("code")!.textContent).toContain(
      "http://app.test/invite/",
    );
    // The new invite shows up in the pending list.
    expect(container.textContent).toContain("teammate@example.com");
  });
});

describe("AccessPanel roles tab", () => {
  const ROLES_TAB_PERMS: PermissionKey[] = ["members:read", "roles:manage"];

  it("renders the permission matrix grouped by catalog group", async () => {
    const { container } = await mountAccess(ROLES_TAB_PERMS, {
      members: [selfAdmin],
      catalog: CATALOG,
      rolePermissions: ROLE_PERMS,
    });
    await openTab(container, "Roles & permissions");
    await waitFor(() => container.textContent!.includes("Update workspace"));

    for (const group of ["Workspace", "Members", "Invites"]) {
      expect(container.textContent).toContain(group);
    }
    for (const def of CATALOG) {
      expect(container.textContent).toContain(def.label);
      expect(container.textContent).toContain(def.description);
    }
    // One switch per role per permission.
    expect(container.querySelectorAll('[data-slot="switch"]').length).toBe(
      CATALOG.length * 3,
    );
  });

  it("disables locked admin switches but not other cells", async () => {
    const { container } = await mountAccess(ROLES_TAB_PERMS, {
      members: [selfAdmin],
      catalog: CATALOG,
      rolePermissions: ROLE_PERMS,
    });
    await openTab(container, "Roles & permissions");
    await waitFor(() => container.textContent!.includes("Update workspace"));

    const switchFor = (label: string) =>
      container.querySelector<HTMLButtonElement>(
        `[data-slot="switch"][aria-label="${label}"]`,
      )!;

    // tenant:update and members:assign_role are locked for admin.
    expect(switchFor("Admin: Update workspace").disabled).toBe(true);
    expect(switchFor("Admin: Assign roles").disabled).toBe(true);
    // members:remove is not locked, and other roles are always editable.
    expect(switchFor("Admin: Remove members").disabled).toBe(false);
    expect(switchFor("Manager: Update workspace").disabled).toBe(false);
    // Granted state reflects the fetched role permissions.
    expect(switchFor("Admin: Remove members").dataset.state).toBe("checked");
    expect(switchFor("Manager: Remove members").dataset.state).toBe("unchecked");
  });

  it("enables Save after a toggle and PUTs the dirty role", async () => {
    const { container, calls } = await mountAccess(ROLES_TAB_PERMS, {
      members: [selfAdmin],
      catalog: CATALOG,
      rolePermissions: ROLE_PERMS,
    });
    await openTab(container, "Roles & permissions");
    await waitFor(() => container.textContent!.includes("Update workspace"));

    const save = findButton(container, "Save changes")!;
    expect(save.disabled).toBe(true);

    const managerRemove = container.querySelector<HTMLButtonElement>(
      '[data-slot="switch"][aria-label="Manager: Remove members"]',
    )!;
    await userEvent.click(managerRemove);
    await waitFor(() => managerRemove.dataset.state === "checked");
    expect(save.disabled).toBe(false);

    await userEvent.click(save);
    await waitFor(() => container.textContent!.includes("Saved."));

    const puts = calls.filter((c) => c.method === "PUT");
    expect(puts).toHaveLength(1);
    expect(puts[0].path).toBe("/api/v1/tenants/tenant-1/roles/manager");
    const body = puts[0].body as { permissions: PermissionKey[] };
    expect(body.permissions.sort()).toEqual(["invites:read", "members:remove"]);
  });
});
