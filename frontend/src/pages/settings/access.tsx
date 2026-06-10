import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useInvitableRoles, usePermission } from "@/hooks/use-permission";
import { ApiError } from "@/lib/api";
import { createInvite, listInvites, revokeInvite, type Invite } from "@/lib/invites";
import {
  assignMemberRole,
  listMembers,
  removeMember,
  type Member,
} from "@/lib/members";
import {
  LOCKED_ADMIN_PERMISSIONS,
  ROLE_LABELS,
  ROLES,
  type PermissionKey,
  type Role,
} from "@/lib/permissions";
import {
  getPermissionCatalog,
  listRolePermissions,
  updateRolePermissions,
  type PermissionDefinition,
} from "@/lib/roles";
import { useAuth } from "@/providers/auth-provider";
import { useTenant } from "@/providers/tenant-provider";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function AccessPage() {
  const { token } = useAuth();
  const { tenant, refresh } = useTenant();
  const canManageRoles = usePermission("roles:manage");
  const canReadInvites = usePermission("invites:read");
  const invitableRoles = useInvitableRoles();
  const showInvites = canReadInvites || invitableRoles.length > 0;

  if (!token || !tenant) return null;

  return (
    <main className="mx-auto min-h-svh max-w-6xl px-6 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-semibold tracking-tight">Access</h1>
        <p className="text-muted-foreground mt-2 max-w-2xl">
          Manage who belongs to {tenant.name}, what role they hold, and what each role
          can do.
        </p>
      </header>

      <Tabs defaultValue="members">
        <TabsList>
          <TabsTrigger value="members">Members</TabsTrigger>
          {showInvites && <TabsTrigger value="invites">Invites</TabsTrigger>}
          {canManageRoles && (
            <TabsTrigger value="roles">Roles &amp; permissions</TabsTrigger>
          )}
        </TabsList>
        <TabsContent value="members">
          <MembersTab token={token} tenantId={tenant.id} />
        </TabsContent>
        {showInvites && (
          <TabsContent value="invites">
            <InvitesTab token={token} tenantId={tenant.id} />
          </TabsContent>
        )}
        {canManageRoles && (
          <TabsContent value="roles">
            <RolesTab
              token={token}
              tenantId={tenant.id}
              onSaved={() => void refresh()}
            />
          </TabsContent>
        )}
      </Tabs>
    </main>
  );
}

// --------------------------------------------------------------------------
// Members
// --------------------------------------------------------------------------

function MembersTab({ token, tenantId }: { token: string; tenantId: string }) {
  const { user } = useAuth();
  const canAssign = usePermission("members:assign_role");
  const canRemove = usePermission("members:remove");
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const loaded = await listMembers(token, tenantId);
        if (!cancelled) setMembers(loaded);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load members.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId]);

  const adminCount = useMemo(
    () => (members ?? []).filter((m) => m.role === "admin").length,
    [members],
  );

  async function changeRole(member: Member, role: Role) {
    setBusyUserId(member.user_id);
    setError(null);
    try {
      const updated = await assignMemberRole(token, tenantId, member.user_id, role);
      setMembers(
        (prev) =>
          prev?.map((m) => (m.user_id === updated.user_id ? updated : m)) ?? null,
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the role.");
    } finally {
      setBusyUserId(null);
    }
  }

  async function remove(member: Member) {
    setBusyUserId(member.user_id);
    setError(null);
    try {
      await removeMember(token, tenantId, member.user_id);
      setMembers((prev) => prev?.filter((m) => m.user_id !== member.user_id) ?? null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove the member.");
    } finally {
      setBusyUserId(null);
    }
  }

  if (error && !members) {
    return <TabError message={error} />;
  }
  if (!members) {
    return <TabLoading />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Members</CardTitle>
        <CardDescription>
          {members.length} member{members.length === 1 ? "" : "s"} in this workspace.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error && <p className="text-destructive mb-4 text-sm">{error}</p>}
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Member</TableHead>
              <TableHead>GitHub</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead>Role</TableHead>
              {canRemove && <TableHead className="w-24" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member) => {
              const isSelf = member.user_id === user?.id;
              const isLastAdmin = member.role === "admin" && adminCount === 1;
              return (
                <TableRow key={member.user_id}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span>{member.name ?? member.email}</span>
                      <span className="text-muted-foreground text-xs">
                        {member.email}
                        {isSelf && " (you)"}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    {member.github_login ? (
                      <Badge variant="secondary">{member.github_login}</Badge>
                    ) : (
                      <span className="text-muted-foreground text-xs">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {formatDate(member.created_at)}
                  </TableCell>
                  <TableCell>
                    {canAssign && !isLastAdmin ? (
                      <Select
                        value={member.role}
                        disabled={busyUserId === member.user_id}
                        onValueChange={(role) => void changeRole(member, role as Role)}
                      >
                        <SelectTrigger size="sm" className="w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((role) => (
                            <SelectItem key={role} value={role}>
                              {ROLE_LABELS[role]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Badge variant="outline">{ROLE_LABELS[member.role]}</Badge>
                    )}
                  </TableCell>
                  {canRemove && (
                    <TableCell className="text-right">
                      {!isSelf && !isLastAdmin && (
                        <RemoveMemberDialog
                          member={member}
                          busy={busyUserId === member.user_id}
                          onConfirm={() => void remove(member)}
                        />
                      )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function RemoveMemberDialog({
  member,
  busy,
  onConfirm,
}: {
  member: Member;
  busy: boolean;
  onConfirm: () => void;
}) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" disabled={busy} analyticsName="remove_member">
          Remove
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remove member</DialogTitle>
          <DialogDescription>
            Remove {member.name ?? member.email} from this workspace? They will lose
            access immediately.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" analyticsName="remove_member_cancel">
              Cancel
            </Button>
          </DialogClose>
          <DialogClose asChild>
            <Button
              variant="destructive"
              analyticsName="remove_member_confirm"
              onClick={onConfirm}
            >
              Remove
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// --------------------------------------------------------------------------
// Invites
// --------------------------------------------------------------------------

function InvitesTab({ token, tenantId }: { token: string; tenantId: string }) {
  const canRead = usePermission("invites:read");
  const canRevoke = usePermission("invites:revoke");
  const invitableRoles = useInvitableRoles();
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(canRead);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role | "">(
    invitableRoles.includes("individual") ? "individual" : (invitableRoles[0] ?? ""),
  );
  const [sending, setSending] = useState(false);
  const [lastInviteUrl, setLastInviteUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!canRead) return;
    let cancelled = false;
    (async () => {
      try {
        const loaded = await listInvites(token, tenantId);
        if (!cancelled) setInvites(loaded);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof ApiError ? err.message : "Could not load invites.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId, canRead]);

  async function sendInvite(event: React.FormEvent) {
    event.preventDefault();
    if (!email || !role) return;
    setSending(true);
    setError(null);
    setLastInviteUrl(null);
    setCopied(false);
    try {
      const created = await createInvite(token, tenantId, { email, role });
      setInvites((prev) => [created.invite, ...prev]);
      setLastInviteUrl(created.invite_url);
      setEmail("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the invite.");
    } finally {
      setSending(false);
    }
  }

  async function revoke(invite: Invite) {
    setError(null);
    try {
      await revokeInvite(token, tenantId, invite.id);
      setInvites((prev) => prev.filter((i) => i.id !== invite.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not revoke the invite.");
    }
  }

  async function copyInviteUrl() {
    if (!lastInviteUrl) return;
    try {
      await navigator.clipboard.writeText(lastInviteUrl);
      setCopied(true);
    } catch {
      // Clipboard unavailable; the URL is still visible for manual copy.
    }
  }

  return (
    <div className="space-y-6">
      {invitableRoles.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Invite someone</CardTitle>
            <CardDescription>
              They&apos;ll receive a link to join this workspace with the role you pick.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-wrap items-end gap-3"
              onSubmit={(e) => void sendInvite(e)}
            >
              <div className="flex min-w-56 flex-1 flex-col gap-2">
                <Label htmlFor="invite-email">Email</Label>
                <Input
                  id="invite-email"
                  type="email"
                  required
                  placeholder="teammate@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Role</Label>
                <Select value={role} onValueChange={(value) => setRole(value as Role)}>
                  <SelectTrigger className="w-36">
                    <SelectValue placeholder="Role" />
                  </SelectTrigger>
                  <SelectContent>
                    {invitableRoles.map((r) => (
                      <SelectItem key={r} value={r}>
                        {ROLE_LABELS[r]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" disabled={sending} analyticsName="send_invite">
                {sending ? "Sending…" : "Send invite"}
              </Button>
            </form>
            {lastInviteUrl && (
              <div className="bg-muted mt-4 flex items-center justify-between gap-3 rounded-lg p-3">
                <code className="truncate text-xs">{lastInviteUrl}</code>
                <Button
                  variant="outline"
                  size="sm"
                  analyticsName="copy_invite_link"
                  onClick={() => void copyInviteUrl()}
                >
                  {copied ? "Copied" : "Copy link"}
                </Button>
              </div>
            )}
            {error && <p className="text-destructive mt-3 text-sm">{error}</p>}
          </CardContent>
        </Card>
      )}

      {canRead && (
        <Card>
          <CardHeader>
            <CardTitle>Pending invites</CardTitle>
            <CardDescription>
              Invitations that haven&apos;t been accepted yet.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-24 rounded-xl" />
            ) : invites.length === 0 ? (
              <p className="text-muted-foreground text-sm">No pending invites.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Expires</TableHead>
                    {canRevoke && <TableHead className="w-24" />}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {invites.map((invite) => (
                    <TableRow key={invite.id}>
                      <TableCell>{invite.email}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{ROLE_LABELS[invite.role]}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {formatDate(invite.expires_at)}
                      </TableCell>
                      {canRevoke && (
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            analyticsName="revoke_invite"
                            onClick={() => void revoke(invite)}
                          >
                            Revoke
                          </Button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
// Roles & permissions
// --------------------------------------------------------------------------

type RoleGrants = Record<Role, Set<PermissionKey>>;

function RolesTab({
  token,
  tenantId,
  onSaved,
}: {
  token: string;
  tenantId: string;
  onSaved: () => void;
}) {
  const [catalog, setCatalog] = useState<PermissionDefinition[] | null>(null);
  const [grants, setGrants] = useState<RoleGrants | null>(null);
  const [dirtyRoles, setDirtyRoles] = useState<Set<Role>>(new Set());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [defs, rolePerms] = await Promise.all([
          getPermissionCatalog(token),
          listRolePermissions(token, tenantId),
        ]);
        if (cancelled) return;
        setCatalog(defs);
        const next = Object.fromEntries(
          rolePerms.map((rp) => [rp.role, new Set(rp.permissions)]),
        ) as RoleGrants;
        setGrants(next);
        setDirtyRoles(new Set());
      } catch (err) {
        if (!cancelled)
          setError(
            err instanceof ApiError ? err.message : "Could not load role permissions.",
          );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, tenantId]);

  const groups = useMemo(() => {
    if (!catalog) return [];
    const byGroup = new Map<string, PermissionDefinition[]>();
    for (const def of catalog) {
      const list = byGroup.get(def.group) ?? [];
      list.push(def);
      byGroup.set(def.group, list);
    }
    return [...byGroup.entries()];
  }, [catalog]);

  function toggle(role: Role, key: PermissionKey, granted: boolean) {
    setSaved(false);
    setGrants((prev) => {
      if (!prev) return prev;
      const next = { ...prev, [role]: new Set(prev[role]) };
      if (granted) next[role].add(key);
      else next[role].delete(key);
      return next;
    });
    setDirtyRoles((prev) => new Set(prev).add(role));
  }

  async function save() {
    if (!grants) return;
    setSaving(true);
    setError(null);
    try {
      for (const role of dirtyRoles) {
        await updateRolePermissions(token, tenantId, role, [...grants[role]]);
      }
      setDirtyRoles(new Set());
      setSaved(true);
      onSaved();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not save role permissions.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (error && !grants) {
    return <TabError message={error} />;
  }
  if (!catalog || !grants) {
    return <TabLoading />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Roles &amp; permissions</CardTitle>
        <CardDescription>
          Control what each role can do in this workspace. Some admin permissions are
          locked so admins can&apos;t lock themselves out.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Permission</TableHead>
              {ROLES.map((role) => (
                <TableHead key={role} className="w-28 text-center">
                  {ROLE_LABELS[role]}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.map(([group, defs]) => (
              <GroupRows
                key={group}
                group={group}
                defs={defs}
                grants={grants}
                onToggle={toggle}
              />
            ))}
          </TableBody>
        </Table>
        <div className="flex items-center gap-3">
          <Button
            disabled={dirtyRoles.size === 0 || saving}
            analyticsName="save_role_permissions"
            onClick={() => void save()}
          >
            {saving ? "Saving…" : "Save changes"}
          </Button>
          {saved && dirtyRoles.size === 0 && (
            <span className="text-muted-foreground text-sm">Saved.</span>
          )}
          {error && <span className="text-destructive text-sm">{error}</span>}
        </div>
      </CardContent>
    </Card>
  );
}

function GroupRows({
  group,
  defs,
  grants,
  onToggle,
}: {
  group: string;
  defs: PermissionDefinition[];
  grants: RoleGrants;
  onToggle: (role: Role, key: PermissionKey, granted: boolean) => void;
}) {
  return (
    <>
      <TableRow className="hover:bg-transparent">
        <TableCell
          colSpan={1 + ROLES.length}
          className="text-muted-foreground pt-5 text-xs font-medium tracking-wide uppercase"
        >
          {group}
        </TableCell>
      </TableRow>
      {defs.map((def) => (
        <TableRow key={def.key}>
          <TableCell>
            <div className="flex flex-col">
              <span className="text-sm">{def.label}</span>
              <span className="text-muted-foreground text-xs">{def.description}</span>
            </div>
          </TableCell>
          {ROLES.map((role) => {
            const locked =
              role === "admin" && LOCKED_ADMIN_PERMISSIONS.includes(def.key);
            return (
              <TableCell key={role} className="text-center">
                <Switch
                  checked={grants[role].has(def.key)}
                  disabled={locked}
                  aria-label={`${ROLE_LABELS[role]}: ${def.label}`}
                  onCheckedChange={(checked) => onToggle(role, def.key, checked)}
                />
              </TableCell>
            );
          })}
        </TableRow>
      ))}
    </>
  );
}

// --------------------------------------------------------------------------
// Shared bits
// --------------------------------------------------------------------------

function TabLoading() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-24 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}

function TabError({ message }: { message: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Couldn&apos;t load</CardTitle>
        <CardDescription>{message}</CardDescription>
      </CardHeader>
    </Card>
  );
}
