"""Copilot metrics availability probe.

A cheap pre-flight check the orchestrator runs before shelling out to the
`copilot_sync` Meltano job: orgs without Copilot Business (or with the metrics
API policy disabled, or where the App lacks the "Organization Copilot metrics:
Read" permission) get 404/403/422 from the metrics endpoint, so the job can be
skipped instead of running a tap that has nothing to pull.
"""

from __future__ import annotations

import logging
from http import HTTPStatus

import httpx

from app.integrations.github.app_auth import GITHUB_API

logger = logging.getLogger("propel.integrations.github")

# Expected "Copilot not available" responses: 404 (no Copilot Business or
# missing App permission), 403 (forbidden), 422 (metrics API policy disabled).
_UNAVAILABLE_STATUSES = frozenset(
    {HTTPStatus.NOT_FOUND, HTTPStatus.FORBIDDEN, HTTPStatus.UNPROCESSABLE_ENTITY}
)


async def copilot_metrics_available(token: str, org: str) -> bool:
    """Return True when the org's Copilot metrics endpoint is queryable.

    A 200 (even with an empty body) means metrics are available. The expected
    "no Copilot" statuses and any unexpected failure (5xx, network error) all
    return False — skipping the sync is always safer than failing or hanging
    the whole ingestion run.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"{GITHUB_API}/orgs/{org}/copilot/metrics?per_page=1"
    extra = {"event": "github.copilot_probe", "github.org": org}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning(
            "Copilot metrics probe failed; treating Copilot as unavailable",
            extra={**extra, "error.message": str(exc)},
        )
        return False

    if response.status_code == HTTPStatus.OK:
        return True

    expected = response.status_code in _UNAVAILABLE_STATUSES
    level = logging.INFO if expected else logging.WARNING
    logger.log(
        level,
        "Copilot metrics not available for org",
        extra={**extra, "http.status_code": response.status_code},
    )
    return False
