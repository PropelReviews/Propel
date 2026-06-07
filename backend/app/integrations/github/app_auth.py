"""GitHub App authentication for ingestion.

Mints a short-lived app JWT (RS256) from the app private key and exchanges it for
a per-installation access token. Installation tokens are never persisted: the
orchestrator mints one fresh before each Meltano run and passes it through the
environment (see app/ingestion).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

import httpx
import jwt

from app.config import get_settings

logger = logging.getLogger("propel.integrations.github")

GITHUB_API = "https://api.github.com"
# GitHub rejects app JWTs with exp more than 10 minutes out; stay well under.
_APP_JWT_TTL_SECONDS = 540


class GitHubAppAuthError(RuntimeError):
    """Raised when app credentials are missing or token exchange fails."""


@dataclass
class InstallationToken:
    token: str
    expires_at: datetime


def _normalize_private_key(raw: str) -> str:
    # Allow the PEM to be provided with literal "\n" escapes (common in env vars).
    return raw.replace("\\n", "\n").strip()


def mint_app_jwt() -> str:
    settings = get_settings()
    if not settings.github_app_id or not settings.github_app_private_key:
        logger.error(
            "GitHub App credentials are not configured",
            extra={"event": "github.app_auth", "error.message": "missing_credentials"},
        )
        raise GitHubAppAuthError(
            "GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be configured."
        )
    now = int(time.time())
    payload = {
        "iat": now - 60,  # clock-skew allowance
        "exp": now + _APP_JWT_TTL_SECONDS,
        "iss": settings.github_app_id,
    }
    return jwt.encode(
        payload,
        _normalize_private_key(settings.github_app_private_key),
        algorithm="RS256",
    )


async def get_installation(installation_id: str) -> dict:
    """Fetch installation metadata (account login, permissions) via the app JWT."""
    app_jwt = mint_app_jwt()
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API}/app/installations/{installation_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
    if response.status_code != 200:
        logger.error(
            "GitHub installation lookup failed",
            extra={
                "event": "github.app_auth",
                "github.installation_id": installation_id,
                "http.status_code": response.status_code,
            },
        )
        raise GitHubAppAuthError(
            f"Installation lookup failed ({response.status_code}): {response.text}"
        )
    return response.json()


async def get_installation_token(installation_id: str) -> InstallationToken:
    """Exchange the app JWT for an installation access token (~1 hour TTL)."""
    app_jwt = mint_app_jwt()
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers)
    if response.status_code != 201:
        logger.error(
            "GitHub installation token exchange failed",
            extra={
                "event": "github.app_auth",
                "github.installation_id": installation_id,
                "http.status_code": response.status_code,
            },
        )
        raise GitHubAppAuthError(
            f"Installation token exchange failed ({response.status_code}): "
            f"{response.text}"
        )
    body = response.json()
    return InstallationToken(
        token=body["token"],
        expires_at=datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")),
    )


def _next_page_url(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        if any('rel="next"' in seg.strip() for seg in segments[1:]):
            return url
    return None


async def list_installation_repositories(token: str) -> list[str]:
    """List `org/repo` full names accessible to an installation token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[str] = []
    url: str | None = f"{GITHUB_API}/installation/repositories?per_page=100"
    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.error(
                    "GitHub repository listing failed",
                    extra={
                        "event": "github.app_auth",
                        "http.status_code": response.status_code,
                    },
                )
                raise GitHubAppAuthError(
                    f"Repository listing failed ({response.status_code}): "
                    f"{response.text}"
                )
            body = response.json()
            for repo in body.get("repositories", []):
                if repo.get("full_name"):
                    repos.append(repo["full_name"])
            url = _next_page_url(response.headers.get("link"))
    return repos


async def list_org_admin_logins(token: str, org: str) -> set[str]:
    """Return the set of org member logins whose role is `admin` (org owners).

    The `organization_members` stream does not expose role, so admins are
    resolved separately via `GET /orgs/{org}/members?role=admin`. Requires the
    installation to have Organization → Members: Read-only permission.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    admins: set[str] = set()
    url: str | None = f"{GITHUB_API}/orgs/{org}/members?role=admin&per_page=100"
    async with httpx.AsyncClient(timeout=30.0) as client:
        while url:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                logger.error(
                    "GitHub org admin listing failed",
                    extra={
                        "event": "github.app_auth",
                        "github.org": org,
                        "http.status_code": response.status_code,
                    },
                )
                raise GitHubAppAuthError(
                    f"Org admin listing failed ({response.status_code}): "
                    f"{response.text}"
                )
            for member in response.json():
                if member.get("login"):
                    admins.add(str(member["login"]))
            url = _next_page_url(response.headers.get("link"))
    return admins
