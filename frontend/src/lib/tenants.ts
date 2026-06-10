// Shapes mirror the backend tenants API (app/schemas/roles.py).

import { authedGet } from "@/lib/api";
import type { PermissionKey, Role } from "@/lib/permissions";

export type Tenant = {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  role: Role;
  permissions: PermissionKey[];
};

export function listTenants(token: string): Promise<Tenant[]> {
  return authedGet<Tenant[]>("/api/v1/tenants/", token);
}
