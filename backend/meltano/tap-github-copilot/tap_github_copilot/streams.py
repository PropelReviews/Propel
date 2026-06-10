"""Copilot usage stream.

Pulls the GitHub org Copilot metrics endpoint, which returns one object per day
for roughly the last 28 days (GitHub restates the most recent ~2 days). Each day
is emitted as one record; target-propel maps it to a `copilot.usage` measurement
keyed by (subject, period_start), so restatements upsert rather than double-count.

The org metrics endpoint is aggregate (subject = org). Per-user breakdown is a
follow-up: when seat-level activity is wired in, records can carry `user_login`
and target-propel will key the measurement per user with no target changes.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.streams import RESTStream

if TYPE_CHECKING:
    from collections.abc import Iterable

    import requests

# Daily metrics object is large and nested; landing keeps the full payload in
# raw_record, so the schema is permissive rather than exhaustive.
_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "date": {"type": ["string", "null"]},
        "total_active_users": {"type": ["integer", "null"]},
        "total_engaged_users": {"type": ["integer", "null"]},
    },
}


# Expected "Copilot not available" responses: 404 (no Copilot Business or
# missing App permission), 403 (forbidden), 422 (metrics API policy disabled).
_NO_COPILOT_STATUSES = frozenset(
    {HTTPStatus.NOT_FOUND, HTTPStatus.FORBIDDEN, HTTPStatus.UNPROCESSABLE_ENTITY}
)


class CopilotUsageStream(RESTStream):
    name = "copilot_usage"
    url_base = "https://api.github.com"
    primary_keys = ("date",)  # noqa: RUF012 — singer-sdk expects a sequence
    records_jsonpath = "$[*]"
    schema = _SCHEMA
    # Bound each request so a stalled connection can't hang the Meltano run
    # (singer-sdk's default is 300s).
    timeout = 30

    @property
    def path(self) -> str:
        return f"/orgs/{self.config['org']}/copilot/metrics"

    @property
    def authenticator(self) -> BearerTokenAuthenticator:
        return BearerTokenAuthenticator.create_for_stream(
            self, token=self.config["auth_token"]
        )

    @property
    def http_headers(self) -> dict:
        headers = super().http_headers
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
        return headers

    def validate_response(self, response: requests.Response) -> None:
        # GitHub signals "no Copilot for this org" with 404 (no Copilot
        # Business/Enterprise or missing App permission), 403 (forbidden), or
        # 422 (metrics API policy disabled). Those are expected "no data"
        # states for many orgs, not fatal errors — let the run finish cleanly
        # with zero records instead of failing every hour.
        if response.status_code in _NO_COPILOT_STATUSES:
            return
        super().validate_response(response)

    def parse_response(self, response: requests.Response) -> Iterable[dict]:
        # Only the 200 body is a metrics array; on the tolerated no-Copilot
        # statuses the body is an error object, so emit nothing rather than
        # parsing it as records.
        if response.status_code != HTTPStatus.OK:
            return
        yield from super().parse_response(response)
