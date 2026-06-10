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

export function listInvites(token: string, tenantId: string): Promise<Invite[]> {
  return authedGet<Invite[]>(`/api/v1/tenants/${tenantId}/invites`, token);
}

export function createInvite(
  token: string,
  tenantId: string,
  input: { email: string; role: Role },
): Promise<InviteCreated> {
  return authedRequest<InviteCreated>(
    "POST",
    `/api/v1/tenants/${tenantId}/invites`,
    token,
    input,
  );
}

export function revokeInvite(
  token: string,
  tenantId: string,
  inviteId: string,
): Promise<null> {
  return authedRequest<null>(
    "DELETE",
    `/api/v1/tenants/${tenantId}/invites/${inviteId}`,
    token,
  );
}

export function acceptInvite(
  token: string,
  inviteToken: string,
): Promise<InviteAccepted> {
  return authedRequest<InviteAccepted>(
    "POST",
    `/api/v1/invites/${inviteToken}/accept`,
    token,
  );
}
