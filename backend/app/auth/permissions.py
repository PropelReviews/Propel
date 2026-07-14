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
        key="invites:role:individual",
        label="Invite individuals",
        description="Send invitations with the individual role.",
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
        key="metrics:manage",
        label="Manage metric definitions",
        description="Create, activate, and archive org metric definitions and sets.",
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

# Permissions the admin role can never lose — prevents locking every admin
# out of role/member management via the UI.
LOCKED_ADMIN_PERMISSIONS: frozenset[str] = frozenset(
    {"tenant:update", "members:assign_role", "roles:manage"}
)

INVITE_ROLE_PERMISSIONS: dict[Role, str] = {
    Role.admin: "invites:role:admin",
    Role.manager: "invites:role:manager",
    Role.individual: "invites:role:individual",
}

# Default matrix — mirrors the pre-configurable hardcoded behavior.
DEFAULT_ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.admin: ALL_PERMISSION_KEYS,
    Role.manager: frozenset(
        {
            "tenant:read",
            "members:read",
            "invites:read",
            "invites:revoke",
            "invites:role:manager",
            "invites:role:individual",
            "ingestion:read",
            "metrics:read",
        }
    ),
    Role.individual: frozenset(
        {
            "tenant:read",
            "members:read",
            "ingestion:read",
            "metrics:read",
        }
    ),
}
