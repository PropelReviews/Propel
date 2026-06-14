"""Permission catalog and per-role defaults.

Permission keys are stable strings stored per-tenant in
``tenant_role_permissions``; the catalog here is the single source of truth
for which keys exist and how they appear in the admin UI.
"""

from dataclasses import dataclass

from app.models.enums import Role


@dataclass(frozen=True)
class PermissionDefinition:
    key: str
    label: str
    description: str
    group: str


PERMISSION_CATALOG: tuple[PermissionDefinition, ...] = (
    PermissionDefinition(
        key="tenant:read",
        label="View workspace",
        description="Access the workspace and its basic details.",
        group="Workspace",
    ),
    PermissionDefinition(
        key="tenant:update",
        label="Update workspace",
        description="Rename the workspace or change its slug.",
        group="Workspace",
    ),
    PermissionDefinition(
        key="tenant:delete",
        label="Delete workspace",
        description="Soft-delete the workspace.",
        group="Workspace",
    ),
    PermissionDefinition(
        key="members:read",
        label="View members",
        description="List workspace members and their roles.",
        group="Members",
    ),
    PermissionDefinition(
        key="members:assign_role",
        label="Assign roles",
        description="Change another member's role.",
        group="Members",
    ),
    PermissionDefinition(
        key="members:remove",
        label="Remove members",
        description="Remove a member from the workspace.",
        group="Members",
    ),
    PermissionDefinition(
        key="invites:read",
        label="View invites",
        description="See pending invitations.",
        group="Invites",
    ),
    PermissionDefinition(
        key="invites:revoke",
        label="Revoke invites",
        description="Revoke a pending invitation.",
        group="Invites",
    ),
    PermissionDefinition(
        key="invites:role:owner",
        label="Invite owners",
        description="Send invitations with the owner role.",
        group="Invites",
    ),
    PermissionDefinition(
        key="invites:role:admin",
        label="Invite admins",
        description="Send invitations with the admin role.",
        group="Invites",
    ),
    PermissionDefinition(
        key="invites:role:manager",
        label="Invite managers",
        description="Send invitations with the manager role.",
        group="Invites",
    ),
    PermissionDefinition(
        key="invites:role:member",
        label="Invite members",
        description="Send invitations with the member role.",
        group="Invites",
    ),
    PermissionDefinition(
        key="connections:manage",
        label="Manage tool connections",
        description="Install and manage integrations like the GitHub App.",
        group="Integrations",
    ),
    PermissionDefinition(
        key="github_identities:manage",
        label="Manage GitHub identities",
        description="Link or unlink GitHub org members to Propel users.",
        group="Integrations",
    ),
    PermissionDefinition(
        key="ingestion:read",
        label="View ingestion",
        description="See ingestion runs and stats.",
        group="Data",
    ),
    PermissionDefinition(
        key="metrics:read",
        label="View metrics",
        description="See dashboards and metric data.",
        group="Data",
    ),
    PermissionDefinition(
        key="roles:manage",
        label="Manage role permissions",
        description="Edit which permissions each role grants.",
        group="Roles",
    ),
)

ALL_PERMISSION_KEYS: frozenset[str] = frozenset(p.key for p in PERMISSION_CATALOG)

# Permissions the owner role can never lose — prevents locking every owner
# out of role/member management via the UI.
LOCKED_OWNER_PERMISSIONS: frozenset[str] = frozenset(
    {"tenant:update", "members:assign_role", "roles:manage"}
)

INVITE_ROLE_PERMISSIONS: dict[Role, str] = {
    Role.owner: "invites:role:owner",
    Role.admin: "invites:role:admin",
    Role.manager: "invites:role:manager",
    Role.member: "invites:role:member",
}

DEFAULT_ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.owner: ALL_PERMISSION_KEYS,
    Role.admin: frozenset(
        {
            "tenant:read",
            "tenant:update",
            "members:read",
            "members:assign_role",
            "members:remove",
            "invites:read",
            "invites:revoke",
            "invites:role:admin",
            "invites:role:manager",
            "invites:role:member",
            "connections:manage",
            "github_identities:manage",
            "ingestion:read",
            "metrics:read",
        }
    ),
    Role.manager: frozenset(
        {
            "tenant:read",
            "members:read",
            "invites:read",
            "invites:revoke",
            "invites:role:manager",
            "invites:role:member",
            "ingestion:read",
            "metrics:read",
        }
    ),
    Role.member: frozenset(
        {
            "tenant:read",
            "members:read",
            "ingestion:read",
            "metrics:read",
        }
    ),
}
