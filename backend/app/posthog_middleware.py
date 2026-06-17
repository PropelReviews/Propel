"""PostHog request context for error tracking.

PostHog's Python exception autocapture hooks (``sys.excepthook``) do not fire for
exceptions handled inside the ASGI stack, so we wrap each request in a PostHog
context. Any exception raised while handling the request is captured within that
context — tagged with the route and, when the SPA forwards them, the person's
distinct id and session id — so backend errors link to the same person profiles
and session replays as frontend events.

When PostHog isn't configured the middleware is a transparent pass-through.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.logging_middleware import (
    POSTHOG_DISTINCT_ID_HEADER,
    POSTHOG_SESSION_ID_HEADER,
)
from app.posthog_client import get_client


class PostHogContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        client = get_client()
        if client is None:
            return await call_next(request)

        from posthog import identify_context, set_context_session, tag

        # The context auto-captures exceptions raised within it before re-raising,
        # so the $exception event carries these tags.
        with client.new_context():
            distinct_id = request.headers.get(POSTHOG_DISTINCT_ID_HEADER)
            session_id = request.headers.get(POSTHOG_SESSION_ID_HEADER)
            if distinct_id:
                identify_context(distinct_id)
            if session_id:
                set_context_session(session_id)
            tag("http.method", request.method)
            tag("http.route", request.url.path)
            return await call_next(request)
