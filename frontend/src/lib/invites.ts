// Shapes mirror the backend invites API (app/schemas/invite.py).

import { authedGet, authedRequest } from "@/lib/api";
import type { Role } from "@/lib/permissions";

export type Invite = {
  id: string;
  email: string;
  role: Role;
  expires_at: string;
  created_at: string;
  invited_by_user_id: string | null;
};

export type InviteCreated = {
  invite: Invite;
  invite_url: string;
};

export type InviteAccepted = {
  tenant_id: string;
  role: Role;
};

export function listInvites(tenantId: string): Promise<Invite[]> {
  return authedGet<Invite[]>(`/api/v1/tenants/${tenantId}/invites`);
}

export function createInvite(
  tenantId: string,
  input: { email: string; role: Role },
): Promise<InviteCreated> {
  return authedRequest<InviteCreated>(
    "POST",
    `/api/v1/tenants/${tenantId}/invites`,
    input,
  );
}

export function revokeInvite(tenantId: string, inviteId: string): Promise<null> {
  return authedRequest<null>(
    "DELETE",
    `/api/v1/tenants/${tenantId}/invites/${inviteId}`,
  );
}

export function acceptInvite(inviteToken: string): Promise<InviteAccepted> {
  return authedRequest<InviteAccepted>("POST", `/api/v1/invites/${inviteToken}/accept`);
}
