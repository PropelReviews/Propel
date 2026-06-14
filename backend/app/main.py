from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.auth.middleware import AuthSecurityMiddleware
from app.auth.session import get_session_secret
from app.config import get_settings
from app.feature_flags import init_posthog, shutdown_posthog
from app.logging_middleware import RequestLoggingMiddleware
from app.otel_logging import setup_logging, shutdown_logging
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
)
from app.tracing import get_tracer, setup_tracing, shutdown_tracing

settings = get_settings()
tracer = get_tracer("propel-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging_enabled = setup_logging()
    tracing_enabled = setup_tracing(app)
    init_posthog()
    yield
    shutdown_posthog()
    if tracing_enabled:
        shutdown_tracing()
    if logging_enabled:
        shutdown_logging()


app = FastAPI(title="Propel", lifespan=lifespan)

app.add_middleware(RequestLoggingMiddleware)
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


@app.get("/")
def root():
    with tracer.start_as_current_span("root-handler") as span:
        span.set_attribute("endpoint", "root")
        return {"message": "Hello World"}


@app.get("/health")
def health():
    return {"status": "ok"}
