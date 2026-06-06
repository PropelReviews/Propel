"""Server-side PostHog feature flags.

A thin wrapper over the PostHog Python SDK used to gate backend behaviour. The
client is initialised once at app startup (see ``main.py`` lifespan) and torn
down on shutdown. When PostHog isn't configured — local dev, tests, or any
environment without ``POSTHOG_TOKEN`` — flag checks fall back to static
settings so the app keeps working without a network dependency.

Evaluation policy (per product decision): when PostHog *is* configured the flag
is the source of truth and we **fail closed** — a missing flag or a failed
evaluation blocks the gated behaviour rather than silently allowing it.
"""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger("propel.feature_flags")

# Module-level singleton. ``None`` means "PostHog not configured / unavailable",
# in which case callers fall back to static settings.
_client = None


def init_posthog() -> None:
    """Initialise the PostHog client. Safe to call when unconfigured (no-op)."""
    global _client

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
    # definitions in the background), so the hot path makes no network call.
    _client = Posthog(
        project_api_key=settings.posthog_token,
        host=settings.posthog_host,
        personal_api_key=settings.posthog_personal_api_key or None,
        feature_flags_request_timeout_seconds=3,
    )
    logger.info("PostHog feature flags enabled")


def get_client():
    """The shared PostHog client, or ``None`` when PostHog isn't configured.

    Exposed so other modules (e.g. ``posthog_events``) can reuse the same
    client for server-side event capture.
    """
    return _client


def shutdown_posthog() -> None:
    """Flush queued events and stop the background poller."""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None


def is_enabled(flag_key: str, distinct_id: str, *, default: bool) -> bool:
    """Evaluate a boolean flag.

    Falls back to ``default`` when PostHog isn't configured. When it *is*
    configured we fail closed: a missing flag (``None``) or an evaluation error
    resolves to ``False``.
    """
    if _client is None:
        return default

    try:
        enabled = _client.feature_enabled(flag_key, distinct_id)
    except Exception:
        logger.exception(
            "PostHog flag '%s' evaluation failed; failing closed", flag_key
        )
        return False

    return bool(enabled)


def registration_enabled(distinct_id: str) -> bool:
    """Whether server-side signup is currently allowed."""
    settings = get_settings()
    return is_enabled(
        settings.auth_registration_flag,
        distinct_id,
        default=settings.auth_registration_enabled,
    )
