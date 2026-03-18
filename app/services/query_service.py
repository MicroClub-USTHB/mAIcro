import json
from time import perf_counter

from app.core.vector_store import QdrantVectorStore
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk
from app.observability import get_tracer, increment_llm_token_usage
from app.services.ai import GeminiProvider


class QueryService:
    def __init__(self, vector_store: QdrantVectorStore, gemini_provider: GeminiProvider) -> None:
        self.vector_store = vector_store
        self.gemini_provider = gemini_provider
        self.tracer = get_tracer("maicro.query_service")

    def chat(self, payload: ChatRequest) -> ChatResponse:
        with self.tracer.start_as_current_span("rag.pipeline") as pipeline_span:
            with self.tracer.start_as_current_span("rag.embedding") as embedding_span:
                embedding_start = perf_counter()
                query_vector = self.vector_store.embed_query(payload.query)
                embedding_ms = (perf_counter() - embedding_start) * 1000
                embedding_span.set_attribute("rag.embedding.duration_ms", embedding_ms)

            with self.tracer.start_as_current_span("rag.retrieval") as retrieval_span:
                retrieval_start = perf_counter()
                retrieved = self.vector_store.similarity_search_by_vector(
                    query_vector=query_vector,
                    n_results=payload.n_results,
                )
                retrieval_ms = (perf_counter() - retrieval_start) * 1000
                retrieval_span.set_attribute("rag.retrieval.duration_ms", retrieval_ms)
                retrieval_span.set_attribute("rag.retrieval.top_k", len(retrieved))
                retrieval_span.set_attribute(
                    "rag.retrieval.documents",
                    json.dumps(
                        [
                            {
                                "id": str(point.id),
                                "score": float(getattr(point, "score", 0.0) or 0.0),
                                "text_preview": str(
                                    (getattr(point, "payload", None) or {}).get("text")
                                    or (getattr(point, "payload", None) or {}).get("document", "")
                                )[:180],
                            }
                            for point in retrieved
                        ],
                        ensure_ascii=True,
                    ),
                )

            filtered = [
                point
                for point in retrieved
                if float(getattr(point, "score", 0.0) or 0.0) >= payload.min_score
            ]

            with self.tracer.start_as_current_span("rag.generation") as generation_span:
                generation_start = perf_counter()
                generation = self.gemini_provider.generate_with_metadata(
                    query=payload.query,
                    retrieved=filtered,
                    history=payload.history,
                )
                generation_ms = (perf_counter() - generation_start) * 1000
                generation_span.set_attribute("rag.generation.duration_ms", generation_ms)
                generation_span.set_attribute("llm.model", generation.model)
                generation_span.set_attribute("llm.used_fallback", generation.used_fallback)
                generation_span.set_attribute("llm.tokens.input", generation.token_usage.get("input", 0))
                generation_span.set_attribute("llm.tokens.output", generation.token_usage.get("output", 0))
                generation_span.set_attribute("llm.tokens.total", generation.token_usage.get("total", 0))

            increment_llm_token_usage(generation.model, "input", generation.token_usage.get("input", 0))
            increment_llm_token_usage(generation.model, "output", generation.token_usage.get("output", 0))
            increment_llm_token_usage(generation.model, "total", generation.token_usage.get("total", 0))

            pipeline_span.set_attribute("rag.retrieval.filtered_count", len(filtered))

            return ChatResponse(
                answer=generation.text,
                sources=[
                    SourceChunk(
                        id=str(point.id),
                        text=(point.payload or {}).get("text") or (point.payload or {}).get("document", ""),
                        score=float(point.score or 0.0),
                        metadata=point.payload or {},
                    )
                    for point in filtered
                ],
                used_fallback=generation.used_fallback,
            )
