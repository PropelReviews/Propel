import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.auth.middleware import AuthSecurityMiddleware
from app.auth.session import get_session_secret
from app.config import get_settings
from app.logging_middleware import RequestLoggingMiddleware
from app.otel_logging import setup_logging, shutdown_logging
from app.posthog_client import get_client, init_posthog, shutdown_posthog
from app.posthog_middleware import PostHogContextMiddleware
from app.routers import (
    auth,
    connections,
    ingestion,
    invites,
    members,
    metrics,
    roles,
    tenants,
    waitlist,
    zitadel_actions,
)
from app.tracing import get_tracer, setup_tracing, shutdown_tracing

settings = get_settings()
tracer = get_tracer("propel-backend")
logger = logging.getLogger("propel.http")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging_enabled = setup_logging()
    tracing_enabled = setup_tracing(app)
    init_posthog(service_name="propel-backend", in_app_modules=["app"])
    yield
    shutdown_posthog()
    if tracing_enabled:
        shutdown_tracing()
    if logging_enabled:
        shutdown_logging()


app = FastAPI(title="Propel", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(PostHogContextMiddleware)
app.add_middleware(AuthSecurityMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=get_session_secret(),
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site="lax",
    https_only=settings.app_env.lower() in {"production", "prod", "beta"},
)

# Allow the browser SPA (a different origin) to call the API, including the
# preflight OPTIONS request the browser sends before POSTs with a JSON body.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tenants.router)
app.include_router(members.router)
app.include_router(members.github_members_router)
app.include_router(invites.router)
app.include_router(roles.router)
app.include_router(connections.router)
app.include_router(ingestion.router)
app.include_router(metrics.router)
app.include_router(waitlist.router)
app.include_router(zitadel_actions.router)


@app.exception_handler(Exception)
async def capture_unhandled_exception(request: Request, exc: Exception):
    """Capture unexpected 500s to PostHog error tracking, then return a 500.

    The context middleware already captures most exceptions with request tags;
    capture here is an idempotent fallback (the SDK dedupes by exception
    instance) for anything that bypasses the context.
    """
    client = get_client()
    if client is not None:
        client.capture_exception(exc)
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/")
def root():
    with tracer.start_as_current_span("root-handler") as span:
        span.set_attribute("endpoint", "root")
        return {"message": "Hello World"}


@app.get("/health")
def health():
    return {"status": "ok"}
