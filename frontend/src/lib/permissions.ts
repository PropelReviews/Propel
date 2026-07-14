// Role + permission keys mirror the backend catalog
// (app/auth/permissions.py). The catalog endpoint is the source of truth for
// labels/grouping; these types keep client-side checks honest.

export type Role = "admin" | "manager" | "individual";

export const ROLES: Role[] = ["admin", "manager", "individual"];

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Admin",
  manager: "Manager",
  individual: "Individual",
};

export type PermissionKey =
  | "tenant:read"
  | "tenant:update"
  | "tenant:delete"
  | "members:read"
  | "members:assign_role"
  | "members:remove"
  | "invites:read"
  | "invites:revoke"
  | "invites:role:admin"
  | "invites:role:manager"
  | "invites:role:individual"
  | "connections:manage"
  | "github_identities:manage"
  | "ingestion:read"
  | "metrics:read"
  | "metrics:manage"
  | "roles:manage";

/** Permission required to send an invite for each target role. */
export const INVITE_ROLE_PERMISSION: Record<Role, PermissionKey> = {
  admin: "invites:role:admin",
  manager: "invites:role:manager",
  individual: "invites:role:individual",
};

/** Permissions the admin role can never lose (mirrors the backend guard). */
export const LOCKED_ADMIN_PERMISSIONS: PermissionKey[] = [
  "tenant:update",
  "members:assign_role",
  "roles:manage",
];
