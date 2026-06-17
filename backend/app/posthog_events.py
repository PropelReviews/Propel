"""Server-side PostHog event capture.

Reuses the PostHog client initialised by ``app.feature_flags`` (see ``main.py``
lifespan). Capture is best-effort: when PostHog isn't configured or the SDK
errors, the event is dropped with a log line — callers must never fail because
analytics is down.
"""

from __future__ import annotations

import logging

from app.posthog_client import get_client

logger = logging.getLogger("propel.posthog_events")


def capture_event(distinct_id: str, event: str, properties: dict | None = None) -> None:
    client = get_client()
    if client is None:
        return

    try:
        client.capture(event, distinct_id=distinct_id, properties=properties or {})
    except Exception:
        logger.exception("PostHog capture of '%s' failed; dropping event", event)
