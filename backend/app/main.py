from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.tracing import get_tracer, setup_tracing, shutdown_tracing

tracer = get_tracer("propel-backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tracing_enabled = setup_tracing(app)
    yield
    if tracing_enabled:
        shutdown_tracing()


app = FastAPI(title="Propel", lifespan=lifespan)


@app.get("/")
def root():
    with tracer.start_as_current_span("root-handler") as span:
        span.set_attribute("endpoint", "root")
        return {"message": "Hello World"}


@app.get("/health")
def health():
    return {"status": "ok"}
