"""Shared server-side PostHog client.

A single PostHog Python SDK client serves three concerns across the backend and
the Dagster ingestion service:

- **Feature flags** (``app.feature_flags``) — local evaluation via the personal
  API key.
- **Event capture** (``app.posthog_events``) — server-side product events.
- **Error tracking** — unhandled exceptions are autocaptured, and framework
  integrations (FastAPI handler, Dagster op failures) capture handled ones.

The client is initialised once per process. When ``POSTHOG_TOKEN`` is unset —
local dev, tests, or any unconfigured environment — initialisation is a no-op
and ``get_client()`` returns ``None`` so callers degrade gracefully.

Every captured event (including ``$exception``) carries ``super_properties`` so
errors are attributable to an environment, app version, commit, and service —
the same release model the frontend uses (see ``frontend/vite.config.ts``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger("propel.posthog")

# Module-level singleton. ``None`` means "PostHog not configured / unavailable".
_client = None

# Production image WORKDIR (see infrastructure/docker/backend.prod.Dockerfile);
# source is baked at /app/app and /app/orchestration.
_PROD_PROJECT_ROOT = "/app"


def _project_root() -> str:
    """Root path used to resolve in-app stack frames for captured exceptions.

    In the production container the source lives under ``/app``. Locally we
    derive the repo root from this file so stack frames resolve to real paths
    instead of being CWD-dependent.
    """
    if os.path.isdir(_PROD_PROJECT_ROOT):
        return _PROD_PROJECT_ROOT
    # backend/app/posthog_client.py -> repo root is three parents up.
    return str(Path(__file__).resolve().parents[2])


def init_posthog(
    *,
    service_name: str = "propel-backend",
    in_app_modules: list[str] | None = None,
) -> None:
    """Initialise the shared PostHog client. Idempotent; no-op when unconfigured.

    Args:
        service_name: ``service`` super property identifying the process
            (``propel-backend`` or ``propel-ingestion``).
        in_app_modules: Module/package prefixes treated as in-app frames in
            captured exceptions (e.g. ``["app", "propel_orchestration"]``), so
            site-packages noise is marked out-of-app.
    """
    global _client
    if _client is not None:
        return

    settings = get_settings()
    if not settings.posthog_token:
        logger.info("PostHog not configured; feature flags fall back to settings")
        return

    try:
        from posthog import Posthog
    except ImportError:
        logger.warning(
            "posthog package not installed; feature flags fall back to settings"
        )
        return

    # A personal API key lets the SDK evaluate flags locally (it polls flag
    # definitions in the background), so the flag hot path makes no network call.
    _client = Posthog(
        project_api_key=settings.posthog_token,
        host=settings.posthog_host,
        personal_api_key=settings.posthog_personal_api_key or None,
        feature_flags_request_timeout_seconds=3,
        enable_exception_autocapture=True,
        project_root=_project_root(),
        in_app_modules=in_app_modules,
        super_properties={
            "app_environment": settings.app_env,
            "app_version": settings.app_version,
            "git_sha": settings.git_sha,
            "service": service_name,
        },
    )
    logger.info("PostHog enabled (service=%s)", service_name)


def get_client():
    """The shared PostHog client, or ``None`` when PostHog isn't configured."""
    return _client


def shutdown_posthog() -> None:
    """Flush queued events and stop the background poller."""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None
