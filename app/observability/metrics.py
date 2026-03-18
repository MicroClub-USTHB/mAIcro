from prometheus_client import Counter, Histogram

RAG_REQUEST_LATENCY_SECONDS = Histogram(
    "rag_request_latency_seconds",
    "End-to-end latency of RAG requests",
    labelnames=("endpoint", "status"),
)

LLM_TOKEN_USAGE_TOTAL = Counter(
    "llm_token_usage_total",
    "LLM token usage by model and token type",
    labelnames=("model", "token_type"),
)


def observe_rag_request_latency(endpoint: str, status: str, seconds: float) -> None:
    RAG_REQUEST_LATENCY_SECONDS.labels(endpoint=endpoint, status=status).observe(seconds)


def increment_llm_token_usage(model: str, token_type: str, value: int) -> None:
    if value <= 0:
        return
    LLM_TOKEN_USAGE_TOTAL.labels(model=model or "unknown", token_type=token_type).inc(value)
