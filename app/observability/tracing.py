from __future__ import annotations

from typing import Dict, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import settings

_TRACING_CONFIGURED = False


def _parse_headers(raw_headers: Optional[str]) -> Dict[str, str]:
    if not raw_headers:
        return {}
    headers: Dict[str, str] = {}
    for item in raw_headers.split(","):
        part = item.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def configure_tracing() -> None:
    global _TRACING_CONFIGURED
    if _TRACING_CONFIGURED or not settings.OTEL_TRACING_ENABLED:
        return

    resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
    if endpoint:
        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers=_parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _TRACING_CONFIGURED = True


def get_tracer(name: str):
    return trace.get_tracer(name)


def current_trace_id() -> str:
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context or not context.is_valid:
        return ""
    return format(context.trace_id, "032x")
