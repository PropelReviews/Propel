"""HTTP request logging — one structured wide event per request."""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.auth.middleware import get_client_ip

logger = logging.getLogger("propel.http")

# PostHog log attributes for linking to person profiles and session replays.
POSTHOG_DISTINCT_ID_HEADER = "X-PostHog-Distinct-Id"
POSTHOG_SESSION_ID_HEADER = "X-PostHog-Session-Id"

# Skip noisy health probes from request logs.
_QUIET_PATHS = frozenset({"/health"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _QUIET_PATHS:
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            extra = {
                "event": "http.request",
                "http.method": request.method,
                "http.route": request.url.path,
                "http.status_code": status_code,
                "http.duration_ms": duration_ms,
                "client.ip": get_client_ip(request),
            }

            distinct_id = request.headers.get(POSTHOG_DISTINCT_ID_HEADER)
            session_id = request.headers.get(POSTHOG_SESSION_ID_HEADER)
            if distinct_id:
                extra["posthogDistinctId"] = distinct_id
            if session_id:
                extra["sessionId"] = session_id

            if status_code >= 500:
                logger.error("HTTP request failed", extra=extra)
            elif status_code >= 400:
                logger.warning("HTTP request client error", extra=extra)
            else:
                logger.info("HTTP request completed", extra=extra)
