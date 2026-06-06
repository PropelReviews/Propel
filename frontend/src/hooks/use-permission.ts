import {
  INVITE_ROLE_PERMISSION,
  ROLES,
  type PermissionKey,
  type Role,
} from "@/lib/permissions";
import { useTenant } from "@/providers/tenant-provider";

/** Whether the current user holds a permission in the selected tenant. */
export function usePermission(key: PermissionKey): boolean {
  const { permissions } = useTenant();
  return permissions.includes(key);
}

/** Whether the current user holds any of the listed permissions. */
export function useAnyPermission(...keys: PermissionKey[]): boolean {
  const { permissions } = useTenant();
  return keys.some((key) => permissions.includes(key));
}

/** Roles the current user is allowed to send invites for. */
export function useInvitableRoles(): Role[] {
  const { permissions } = useTenant();
  return ROLES.filter((role) => permissions.includes(INVITE_ROLE_PERMISSION[role]));
}
