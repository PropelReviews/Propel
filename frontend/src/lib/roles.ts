// Shapes mirror the backend roles API (app/schemas/roles.py).

import { authedGet, authedRequest } from "@/lib/api";
import type { PermissionKey, Role } from "@/lib/permissions";

export type PermissionDefinition = {
  key: PermissionKey;
  label: string;
  description: string;
  group: string;
};

export type RolePermissions = {
  role: Role;
  permissions: PermissionKey[];
};

export function getPermissionCatalog(): Promise<PermissionDefinition[]> {
  return authedGet<PermissionDefinition[]>("/api/v1/permissions/catalog");
}

export function listRolePermissions(tenantId: string): Promise<RolePermissions[]> {
  return authedGet<RolePermissions[]>(`/api/v1/tenants/${tenantId}/roles`);
}

export function updateRolePermissions(
  tenantId: string,
  role: Role,
  permissions: PermissionKey[],
): Promise<RolePermissions> {
  return authedRequest<RolePermissions>(
    "PUT",
    `/api/v1/tenants/${tenantId}/roles/${role}`,
    { permissions },
  );
}
