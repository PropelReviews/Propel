// Role + permission keys mirror the backend catalog
// (app/auth/permissions.py). The catalog endpoint is the source of truth for
// labels/grouping; these types keep client-side checks honest.

export type Role = "owner" | "admin" | "manager" | "member";

export const ROLES: Role[] = ["owner", "admin", "manager", "member"];

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  admin: "Admin",
  manager: "Manager",
  member: "Member",
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
  | "invites:role:owner"
  | "invites:role:admin"
  | "invites:role:manager"
  | "invites:role:member"
  | "connections:manage"
  | "github_identities:manage"
  | "ingestion:read"
  | "metrics:read"
  | "roles:manage";

/** Permission required to send an invite for each target role. */
export const INVITE_ROLE_PERMISSION: Record<Role, PermissionKey> = {
  owner: "invites:role:owner",
  admin: "invites:role:admin",
  manager: "invites:role:manager",
  member: "invites:role:member",
};

/** Permissions the owner role can never lose (mirrors the backend guard). */
export const LOCKED_OWNER_PERMISSIONS: PermissionKey[] = [
  "tenant:update",
  "members:assign_role",
  "roles:manage",
];

/** @deprecated Use LOCKED_OWNER_PERMISSIONS */
export const LOCKED_ADMIN_PERMISSIONS = LOCKED_OWNER_PERMISSIONS;
