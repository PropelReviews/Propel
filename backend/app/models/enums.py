from enum import StrEnum


class Role(StrEnum):
    admin = "admin"
    manager = "manager"
    individual = "individual"


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
