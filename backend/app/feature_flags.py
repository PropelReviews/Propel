"""Server-side PostHog feature flags.

A thin wrapper over the shared PostHog client (see ``app.posthog_client``) used
to gate backend behaviour. The client is initialised once at app startup (see
``main.py`` lifespan). When PostHog isn't configured — local dev, tests, or any
environment without ``POSTHOG_TOKEN`` — flag checks fall back to static
settings so the app keeps working without a network dependency.

Evaluation policy (per product decision): when PostHog *is* configured the flag
is the source of truth and we **fail closed** — a missing flag or a failed
evaluation blocks the gated behaviour rather than silently allowing it.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.posthog_client import get_client

logger = logging.getLogger("propel.feature_flags")


def is_enabled(flag_key: str, distinct_id: str, *, default: bool) -> bool:
    """Evaluate a boolean flag.

    Falls back to ``default`` when PostHog isn't configured. When it *is*
    configured we fail closed: a missing flag (``None``) or an evaluation error
    resolves to ``False``.
    """
    client = get_client()
    if client is None:
        return default

    try:
        enabled = client.feature_enabled(flag_key, distinct_id)
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
