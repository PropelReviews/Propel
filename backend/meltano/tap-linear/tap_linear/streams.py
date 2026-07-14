"""Linear GraphQL streams.

Pulls workspace primitives from Linear's GraphQL API with cursor pagination.
The orchestrator drives incrementality via ``start_date``; target-propel
dedupes by stable ids. Each stream lands the full payload in raw_record, so
schemas are permissive rather than exhaustive.

Streams:
  - issues — ticket snapshots
  - comments — issue / project discussion comments
  - projects — workspace projects
  - issue_description_edits — IssueHistory rows where the description changed
"""

from __future__ import annotations

from typing import Any, Iterable

import requests
from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.pagination import BaseAPIPaginator
from singer_sdk.streams import GraphQLStream

_ISSUES_QUERY = """
query Issues($first: Int!, $after: String, $filter: IssueFilter) {
  issues(first: $first, after: $after, filter: $filter, orderBy: updatedAt) {
    nodes {
      id
      identifier
      title
      description
      priority
      estimate
      url
      createdAt
      updatedAt
      completedAt
      canceledAt
      state { id name type }
      team { id key name }
      assignee { id name displayName email }
      creator { id name displayName email }
      labels { nodes { id name } }
      project { id name }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_COMMENTS_QUERY = """
query Comments($first: Int!, $after: String, $filter: CommentFilter) {
  comments(first: $first, after: $after, filter: $filter, orderBy: updatedAt) {
    nodes {
      id
      body
      url
      createdAt
      updatedAt
      editedAt
      issueId
      projectId
      parentId
      issue { id identifier }
      project { id name }
      user { id name displayName email }
      externalUser { id name displayName }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_PROJECTS_QUERY = """
query Projects($first: Int!, $after: String, $filter: ProjectFilter) {
  projects(first: $first, after: $after, filter: $filter, orderBy: updatedAt) {
    nodes {
      id
      name
      description
      url
      slugId
      priority
      progress
      scope
      health
      createdAt
      updatedAt
      startedAt
      completedAt
      canceledAt
      targetDate
      startDate
      status { id name type }
      lead { id name displayName email }
      creator { id name displayName email }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

# Description edits live on IssueHistory (no top-level connection). Walk issues
# updated since the watermark and flatten history rows where updatedDescription.
_DESCRIPTION_EDITS_QUERY = """
query IssueDescriptionEdits($first: Int!, $after: String, $filter: IssueFilter) {
  issues(first: $first, after: $after, filter: $filter, orderBy: updatedAt) {
    nodes {
      id
      identifier
      url
      history(first: 100) {
        nodes {
          id
          createdAt
          updatedDescription
          actor { id name displayName email }
          descriptionUpdatedBy { id name displayName email }
        }
      }
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "id": {"type": ["string", "null"]},
        "identifier": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "null"]},
        "updatedAt": {"type": ["string", "null"]},
        "completedAt": {"type": ["string", "null"]},
        "state": {"type": ["object", "null"]},
        "team": {"type": ["object", "null"]},
        "assignee": {"type": ["object", "null"]},
        "creator": {"type": ["object", "null"]},
    },
}

_COMMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "id": {"type": ["string", "null"]},
        "body": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "null"]},
        "updatedAt": {"type": ["string", "null"]},
        "issueId": {"type": ["string", "null"]},
        "projectId": {"type": ["string", "null"]},
        "user": {"type": ["object", "null"]},
        "issue": {"type": ["object", "null"]},
    },
}

_PROJECT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "id": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "description": {"type": ["string", "null"]},
        "url": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "null"]},
        "updatedAt": {"type": ["string", "null"]},
        "status": {"type": ["object", "null"]},
        "lead": {"type": ["object", "null"]},
        "creator": {"type": ["object", "null"]},
    },
}

_DESCRIPTION_EDIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "id": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "null"]},
        "updatedDescription": {"type": ["boolean", "null"]},
        "issue": {"type": ["object", "null"]},
        "actor": {"type": ["object", "null"]},
        "descriptionUpdatedBy": {
            "type": ["array", "null"],
            "items": {"type": "object"},
        },
    },
}


class _LinearCursorPaginator(BaseAPIPaginator):
    """Follows Linear's `pageInfo { hasNextPage endCursor }` cursor."""

    def __init__(self, connection_key: str) -> None:
        super().__init__(None)
        self._connection_key = connection_key

    def _page_info(self, response: requests.Response) -> dict:
        data = (response.json() or {}).get("data") or {}
        return (data.get(self._connection_key) or {}).get("pageInfo") or {}

    def has_more(self, response: requests.Response) -> bool:
        return bool(self._page_info(response).get("hasNextPage"))

    def get_next(self, response: requests.Response) -> str | None:
        return self._page_info(response).get("endCursor")


class _LinearGraphQLStream(GraphQLStream):
    """Shared auth, pagination, and updatedAt watermark filter."""

    url_base = "https://api.linear.app"
    path = "/graphql"
    primary_keys = ("id",)  # noqa: RUF012 — singer-sdk expects a sequence
    # Bound each request so a stalled connection can't hang the Meltano run.
    timeout = 30
    _PAGE_SIZE = 100
    _connection_key: str

    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        return BearerTokenAuthenticator.create_for_stream(
            self, token=self.config["auth_token"]
        )

    def get_new_paginator(self) -> _LinearCursorPaginator:
        return _LinearCursorPaginator(self._connection_key)

    def _updated_at_filter(self) -> dict | None:
        start_date = self.config.get("start_date")
        if not start_date:
            return None
        # Linear's DateTime scalar wants a full ISO-8601 timestamp; the
        # orchestrator passes a plain date, so widen it to start-of-day UTC.
        if len(str(start_date)) == 10:
            start_date = f"{start_date}T00:00:00.000Z"
        return {"updatedAt": {"gte": start_date}}

    def get_url_params(
        self, context: dict | None, next_page_token: str | None
    ) -> dict[str, Any]:
        variables: dict[str, Any] = {"first": self._PAGE_SIZE}
        if next_page_token:
            variables["after"] = next_page_token
        updated_filter = self._updated_at_filter()
        if updated_filter is not None:
            variables["filter"] = updated_filter
        return variables


class IssuesStream(_LinearGraphQLStream):
    name = "issues"
    _connection_key = "issues"
    records_jsonpath = "$.data.issues.nodes[*]"
    schema = _ISSUE_SCHEMA
    query = _ISSUES_QUERY


class CommentsStream(_LinearGraphQLStream):
    name = "comments"
    _connection_key = "comments"
    records_jsonpath = "$.data.comments.nodes[*]"
    schema = _COMMENT_SCHEMA
    query = _COMMENTS_QUERY


class ProjectsStream(_LinearGraphQLStream):
    name = "projects"
    _connection_key = "projects"
    records_jsonpath = "$.data.projects.nodes[*]"
    schema = _PROJECT_SCHEMA
    query = _PROJECTS_QUERY


class IssueDescriptionEditsStream(_LinearGraphQLStream):
    """Flatten IssueHistory rows where the issue description was edited."""

    name = "issue_description_edits"
    _connection_key = "issues"
    records_jsonpath = "$.data.issues.nodes[*]"
    schema = _DESCRIPTION_EDIT_SCHEMA
    query = _DESCRIPTION_EDITS_QUERY

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        data = (response.json() or {}).get("data") or {}
        issues = (data.get("issues") or {}).get("nodes") or []
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            issue_ref = {
                "id": issue.get("id"),
                "identifier": issue.get("identifier"),
                "url": issue.get("url"),
            }
            history_nodes = ((issue.get("history") or {}).get("nodes")) or []
            for entry in history_nodes:
                if not isinstance(entry, dict):
                    continue
                if not entry.get("updatedDescription"):
                    continue
                if not entry.get("id"):
                    continue
                yield {
                    "id": entry["id"],
                    "createdAt": entry.get("createdAt"),
                    "updatedDescription": True,
                    "issue": issue_ref,
                    "actor": entry.get("actor"),
                    "descriptionUpdatedBy": entry.get("descriptionUpdatedBy"),
                }
