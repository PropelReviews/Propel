"""OpenTelemetry distributed tracing, exported to PostHog.

PostHog ingests standard OTLP/HTTP spans at `<host>/i/v1/traces`, authenticated
with the project token as a bearer header. No PostHog-specific packages are
required.

Tracing degrades gracefully:
- a no-op when ``POSTHOG_TOKEN`` is unset, and
- a no-op when the OpenTelemetry packages are not installed (e.g. before the
  backend image has been rebuilt with the new requirements).
"""

import os
from contextlib import contextmanager


class _NoopSpan:
    def set_attribute(self, *args, **kwargs) -> None:
        pass


class _NoopTracer:
    @contextmanager
    def start_as_current_span(self, *args, **kwargs):
        yield _NoopSpan()


def get_tracer(name: str):
    try:
        from opentelemetry import trace
    except ImportError:
        return _NoopTracer()
    return trace.get_tracer(name)


def setup_tracing(app) -> bool:
    token = os.getenv("POSTHOG_TOKEN")
    if not token:
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        # OpenTelemetry not installed yet; skip tracing without crashing.
        return False

    host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com").rstrip("/")
    service_name = os.getenv("OTEL_SERVICE_NAME", "propel-backend")

    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    exporter = OTLPSpanExporter(
        endpoint=f"{host}/i/v1/traces",
        headers={"Authorization": f"Bearer {token}"},
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-create a span for every incoming HTTP request.
    FastAPIInstrumentor.instrument_app(app)

    return True


def shutdown_tracing() -> None:
    """Flush any queued spans on application shutdown."""
    try:
        from opentelemetry import trace
    except ImportError:
        return

    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
