import time
from collections import defaultdict
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.config import get_settings
from app.feature_flags import registration_enabled

REGISTER_PATH = "/api/v1/auth/register"
LOGIN_PATH = "/api/v1/auth/login"


class SlidingWindowRateLimiter:
    """In-memory per-IP rate limiter for auth endpoints."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def is_allowed(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            hits = [t for t in self._hits[key] if t > cutoff]
            if len(hits) >= max_requests:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


auth_rate_limiter = SlidingWindowRateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class AuthSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path

        if (
            request.method == "POST"
            and path == REGISTER_PATH
            and not registration_enabled(get_client_ip(request))
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "REGISTRATION_DISABLED"},
            )

        if request.method == "POST" and path in {REGISTER_PATH, LOGIN_PATH}:
            client_ip = get_client_ip(request)
            if not auth_rate_limiter.is_allowed(
                f"{path}:{client_ip}",
                max_requests=settings.auth_rate_limit_max_requests,
                window_seconds=settings.auth_rate_limit_window_seconds,
            ):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "TOO_MANY_REQUESTS"},
                    headers={
                        "Retry-After": str(settings.auth_rate_limit_window_seconds)
                    },
                )

        return await call_next(request)
