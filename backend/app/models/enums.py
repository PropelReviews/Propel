import enum


class Role(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    individual = "individual"


class IntegrationProvider(str, enum.Enum):
    """Stub for v2 connected_accounts — tool OAuth, not login."""

    github = "github"
    linear = "linear"
    jira = "jira"
    slack = "slack"
    cursor = "cursor"
