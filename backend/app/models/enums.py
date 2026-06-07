from enum import StrEnum


class Role(StrEnum):
    admin = "admin"
    manager = "manager"
    individual = "individual"


class IntegrationProvider(StrEnum):
    """Stub for v2 connected_accounts — tool OAuth, not login."""

    github = "github"
    linear = "linear"
    jira = "jira"
    slack = "slack"
    cursor = "cursor"
