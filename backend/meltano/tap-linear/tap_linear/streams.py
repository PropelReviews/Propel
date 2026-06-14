"""Linear issues stream (GraphQL).

Pulls issues from Linear's GraphQL API, paginating with cursor-based
`pageInfo`. Issues updated on or after ``start_date`` are returned (the
orchestrator drives incrementality with a watermark; target-propel dedupes by
issue id). Each issue is one record; target-propel maps it to a `linear.issue`
event. Landing keeps the full payload in raw_record, so the schema is permissive
rather than exhaustive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.pagination import BaseAPIPaginator
from singer_sdk.streams import GraphQLStream

if TYPE_CHECKING:
    import requests

_QUERY = """
query Issues($first: Int!, $after: String, $filter: IssueFilter) {
  issues(first: $first, after: $after, filter: $filter, orderBy: updatedAt) {
    nodes {
      id
      identifier
      title
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
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "id": {"type": ["string", "null"]},
        "identifier": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "createdAt": {"type": ["string", "null"]},
        "updatedAt": {"type": ["string", "null"]},
        "completedAt": {"type": ["string", "null"]},
        "state": {"type": ["object", "null"]},
        "team": {"type": ["object", "null"]},
        "assignee": {"type": ["object", "null"]},
        "creator": {"type": ["object", "null"]},
    },
}


class _LinearCursorPaginator(BaseAPIPaginator):
    """Follows Linear's `pageInfo { hasNextPage endCursor }` cursor."""

    def __init__(self) -> None:
        super().__init__(None)

    def _page_info(self, response: requests.Response) -> dict:
        data = (response.json() or {}).get("data") or {}
        return (data.get("issues") or {}).get("pageInfo") or {}

    def has_more(self, response: requests.Response) -> bool:
        return bool(self._page_info(response).get("hasNextPage"))

    def get_next(self, response: requests.Response) -> str | None:
        return self._page_info(response).get("endCursor")


class IssuesStream(GraphQLStream):
    name = "issues"
    url_base = "https://api.linear.app"
    path = "/graphql"
    primary_keys = ("id",)  # noqa: RUF012 — singer-sdk expects a sequence
    records_jsonpath = "$.data.issues.nodes[*]"
    schema = _SCHEMA
    query = _QUERY
    # Bound each request so a stalled connection can't hang the Meltano run.
    timeout = 30
    _PAGE_SIZE = 100

    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        return BearerTokenAuthenticator.create_for_stream(
            self, token=self.config["auth_token"]
        )

    def get_new_paginator(self) -> _LinearCursorPaginator:
        return _LinearCursorPaginator()

    def _filter(self) -> dict | None:
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
        issue_filter = self._filter()
        if issue_filter is not None:
            variables["filter"] = issue_filter
        return variables
