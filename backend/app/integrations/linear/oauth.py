"""Linear OAuth2 (authorization-code) client for the data connection.

Unlike GitHub ingestion (App installation tokens minted per run), Linear uses
the standard authorization-code flow with ``actor=app``: a workspace admin
installs the app once, we exchange the code for an access + refresh token, store
them encrypted on ``connected_accounts``, and refresh the access token before it
expires. The access token is a Bearer credential for Linear's GraphQL API.

Docs: https://linear.app/developers/oauth-2-0-authentication
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.config import get_settings

logger = logging.getLogger("propel.integrations.linear")

AUTHORIZE_URL = "https://linear.app/oauth/authorize"
TOKEN_URL = "https://api.linear.app/oauth/token"
REVOKE_URL = "https://api.linear.app/oauth/revoke"
GRAPHQL_URL = "https://api.linear.app/graphql"

# Read access is all the Issues ingestion needs; `read` is always granted.
DEFAULT_SCOPE = "read"
# Workspace-level install: the token acts as the app, not the installing user
# (the right model for team analytics). Requires a Linear admin to approve.
_ACTOR = "app"
_TIMEOUT = 30.0


class LinearOAuthError(RuntimeError):
    """Raised when Linear OAuth credentials are missing or an exchange fails."""


@dataclass
class LinearToken:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: list[str]


def _require_credentials() -> tuple[str, str]:
    settings = get_settings()
    if not settings.linear_oauth_enabled:
        raise LinearOAuthError(
            "Linear OAuth is not configured "
            "(OAUTH_LINEAR_CLIENT_ID / OAUTH_LINEAR_CLIENT_SECRET)."
        )
    return settings.oauth_linear_client_id, settings.oauth_linear_client_secret


def build_authorize_url(redirect_uri: str, state: str) -> str:
    client_id, _ = _require_credentials()
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": DEFAULT_SCOPE,
        "actor": _ACTOR,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _parse_scopes(raw: object) -> list[str]:
    # Apps created after Dec 2023 return a space-separated string; older ones
    # return an array.
    if isinstance(raw, list):
        return [str(s) for s in raw]
    if isinstance(raw, str):
        return raw.split()
    return []


def _to_token(payload: dict) -> LinearToken:
    access_token = payload.get("access_token")
    if not access_token:
        raise LinearOAuthError("Linear token response did not include an access_token")
    expires_in = payload.get("expires_in")
    expires_at = (
        datetime.now(UTC) + timedelta(seconds=int(expires_in))
        if isinstance(expires_in, (int, float))
        else None
    )
    return LinearToken(
        access_token=str(access_token),
        refresh_token=payload.get("refresh_token"),
        expires_at=expires_at,
        scopes=_parse_scopes(payload.get("scope")),
    )


async def _post_token(data: dict) -> LinearToken:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return _to_token(response.json())
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Linear token request failed",
            extra={
                "event": "linear.oauth",
                "http.status_code": exc.response.status_code,
                "error.message": exc.response.text[:500],
            },
        )
        raise LinearOAuthError("Linear token request failed") from exc
    except httpx.HTTPError as exc:
        logger.error(
            "Linear token request error",
            extra={"event": "linear.oauth", "error.message": str(exc)},
        )
        raise LinearOAuthError("Linear token request error") from exc


async def exchange_code(code: str, redirect_uri: str) -> LinearToken:
    client_id, client_secret = _require_credentials()
    return await _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )


async def refresh_access_token(refresh_token: str) -> LinearToken:
    client_id, client_secret = _require_credentials()
    return await _post_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
    )


async def fetch_workspace(access_token: str) -> tuple[str, str]:
    """Return the (workspace id, workspace name) for an access token.

    Used to populate ``external_account_id`` / ``external_account_name`` so the
    connection is recognizable and uniquely keyed per Linear workspace.
    """
    query = "{ organization { id name } }"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                GRAPHQL_URL,
                json={"query": query},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            org = (response.json().get("data") or {}).get("organization") or {}
    except httpx.HTTPError as exc:
        logger.error(
            "Linear workspace lookup failed",
            extra={"event": "linear.oauth", "error.message": str(exc)},
        )
        raise LinearOAuthError("Could not read the Linear workspace") from exc

    org_id = org.get("id")
    if not org_id:
        raise LinearOAuthError("Linear workspace response did not include an id")
    return str(org_id), str(org.get("name") or org_id)
