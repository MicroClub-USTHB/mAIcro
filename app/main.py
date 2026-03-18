from fastapi import FastAPI, Request
from prometheus_client import make_asgi_app

from app.api.routes.health import router as health_router
from app.api.v1 import api_router
from app.observability import configure_tracing, current_trace_id, get_tracer

configure_tracing()

app = FastAPI(
    title="mAIcro",
    description="Community Intelligence Service - Reusable AI Infrastructure",
    version="0.1.0",
)

http_tracer = get_tracer("maicro.http")


@app.middleware("http")
async def add_trace_id_header(request: Request, call_next):
    with http_tracer.start_as_current_span(f"http {request.method} {request.url.path}") as span:
        response = await call_next(request)
        trace_id = current_trace_id() or format(span.get_span_context().trace_id, "032x")
        if trace_id:
            response.headers["trace_id"] = trace_id
        return response


app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")
app.mount("/metrics", make_asgi_app())
