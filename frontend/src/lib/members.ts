// Shapes mirror the backend members API (app/schemas/membership.py).

import { authedGet, authedRequest } from "@/lib/api";
import type { Role } from "@/lib/permissions";

export type Member = {
  user_id: string;
  email: string;
  name: string | null;
  role: Role;
  created_at: string;
  github_login: string | null;
  github_link_status: string | null;
};

export function listMembers(token: string, tenantId: string): Promise<Member[]> {
  return authedGet<Member[]>(`/api/v1/tenants/${tenantId}/members/`, token);
}

export function assignMemberRole(
  token: string,
  tenantId: string,
  userId: string,
  role: Role,
): Promise<Member> {
  return authedRequest<Member>(
    "PATCH",
    `/api/v1/tenants/${tenantId}/members/${userId}/role`,
    token,
    { role },
  );
}

export function removeMember(
  token: string,
  tenantId: string,
  userId: string,
): Promise<null> {
  return authedRequest<null>(
    "DELETE",
    `/api/v1/tenants/${tenantId}/members/${userId}`,
    token,
  );
}
