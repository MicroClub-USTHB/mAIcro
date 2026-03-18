from time import perf_counter

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_query_service
from app.models.schemas import ChatRequest, ChatResponse
from app.observability import current_trace_id, get_tracer, observe_rag_request_latency
from app.services.query_service import QueryService

router = APIRouter()
tracer = get_tracer("maicro.api.v1")


def _handle_chat(
    payload: ChatRequest,
    response: Response,
    endpoint_path: str,
    query_service: QueryService,
) -> ChatResponse:
    start = perf_counter()
    status = "error"

    with tracer.start_as_current_span("api.ask") as span:
        try:
            result = query_service.chat(payload)
            status = "success"
            return result
        finally:
            elapsed = perf_counter() - start
            observe_rag_request_latency(endpoint=endpoint_path, status=status, seconds=elapsed)
            trace_id = current_trace_id() or format(span.get_span_context().trace_id, "032x")
            if trace_id:
                response.headers["trace_id"] = trace_id


@router.post("/ask", response_model=ChatResponse)
def ask(
    payload: ChatRequest,
    response: Response,
    query_service: QueryService = Depends(get_query_service),
) -> ChatResponse:
    return _handle_chat(payload, response, "/api/v1/ask", query_service)


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    response: Response,
    query_service: QueryService = Depends(get_query_service),
) -> ChatResponse:
    return _handle_chat(payload, response, "/api/v1/chat", query_service)
