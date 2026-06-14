from enum import StrEnum


class Role(StrEnum):
    owner = "owner"
    admin = "admin"
    manager = "manager"
    member = "member"


class MembershipStatus(StrEnum):
    invited = "invited"
    active = "active"
    disabled = "disabled"


class IntegrationProvider(StrEnum):
    """Source provider for a connected_accounts row (tool connection, not login)."""

    github = "github"
    linear = "linear"
    jira = "jira"
    slack = "slack"
    cursor = "cursor"


class AuthType(StrEnum):
    """How a connected account authenticates against its provider."""

    oauth = "oauth"
    github_app_installation = "github_app_installation"


class ConnectionStatus(StrEnum):
    active = "active"
    paused = "paused"
    revoked = "revoked"


class DatapointKind(StrEnum):
    """Discrete occurrence vs periodic aggregate (see ingestion spec §2)."""

    event = "event"
    measurement = "measurement"


class IngestionRunStatus(StrEnum):
    running = "running"
    success = "success"
    error = "error"


class GitHubOrgRole(StrEnum):
    """A member's role within the GitHub organization."""

    admin = "admin"  # GitHub org owner
    member = "member"


class IdentityLinkMethod(StrEnum):
    """How an external identity was connected to a Propel user."""

    oauth_id = "oauth_id"  # matched a github login-OAuth account by provider id
    email = "email"  # matched an existing user by exact email
    provisioned = "provisioned"  # a new Propel user was created for this identity
    manual = "manual"  # an admin linked it explicitly


class IdentityStatus(StrEnum):
    """Linking state of an external identity."""

    linked = "linked"  # attached to an existing Propel user
    provisioned = "provisioned"  # attached to a user we auto-created
    pending_email = "pending_email"  # no email/match yet; awaiting OAuth claim
