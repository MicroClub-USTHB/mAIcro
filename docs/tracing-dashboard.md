# Tracing Dashboard Guide

This project exports traces with OpenTelemetry and metrics with Prometheus.

## 1) Start a local tracing dashboard (Jaeger)

```bash
docker run --rm --name jaeger \
  -p 16686:16686 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

Jaeger UI will be available at `http://localhost:16686`.

## 2) Configure app environment

Add these variables to `.env`:

```env
OTEL_TRACING_ENABLED=true
OTEL_SERVICE_NAME=maicro-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

`OTEL_EXPORTER_OTLP_HEADERS` is optional and supports comma-separated headers (`key=value,key2=value2`).

## 3) Run the API

```bash
uv run uvicorn app.main:app --reload
```

## 4) Generate traces

Call `POST /api/v1/ask` (or `/api/v1/chat`).
Each response includes a `trace_id` header you can use to correlate logs and traces.

## 5) Inspect trace content in Jaeger

For each request, spans include:

- `api.ask`
- `rag.pipeline`
- `rag.embedding` with `rag.embedding.duration_ms`
- `rag.retrieval` with `rag.retrieval.duration_ms`, `rag.retrieval.top_k`, `rag.retrieval.documents`
- `rag.generation` with `rag.generation.duration_ms` and token attributes

## 6) Metrics endpoint

Prometheus metrics are exposed at `GET /metrics`.

Relevant metrics:

- `rag_request_latency_seconds`
- `llm_token_usage_total`
