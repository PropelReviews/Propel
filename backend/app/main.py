from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.middleware import AuthSecurityMiddleware
from app.config import get_settings
from app.feature_flags import init_posthog, shutdown_posthog
from app.routers import auth, connections, ingestion, invites, members, tenants
from app.tracing import get_tracer, setup_tracing, shutdown_tracing

settings = get_settings()
tracer = get_tracer("propel-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tracing_enabled = setup_tracing(app)
    init_posthog()
    yield
    shutdown_posthog()
    if tracing_enabled:
        shutdown_tracing()


app = FastAPI(title="Propel", lifespan=lifespan)

app.add_middleware(AuthSecurityMiddleware)

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
app.include_router(invites.router)
app.include_router(connections.router)
app.include_router(ingestion.router)


@app.get("/")
def root():
    with tracer.start_as_current_span("root-handler") as span:
        span.set_attribute("endpoint", "root")
        return {"message": "Hello World"}


@app.get("/health")
def health():
    return {"status": "ok"}
