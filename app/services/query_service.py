from app.core.vector_store import QdrantVectorStore
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk
from app.services.ai import GeminiProvider


class QueryService:
    def __init__(self, vector_store: QdrantVectorStore, gemini_provider: GeminiProvider) -> None:
        self.vector_store = vector_store
        self.gemini_provider = gemini_provider

    def chat(self, payload: ChatRequest) -> ChatResponse:
        retrieved = self.vector_store.similarity_search(
            query=payload.query,
            n_results=payload.top_k,
        )

        filtered = [
            point
            for point in retrieved
            if float(getattr(point, "score", 0.0) or 0.0) >= payload.min_score
        ]

        answer = self.gemini_provider.generate(
            query=payload.query,
            retrieved=filtered,
            history=payload.history,
        )

        return ChatResponse(
            answer=answer,
            sources=[
                SourceChunk(
                    id=str(point.id),
                    text=(point.payload or {}).get("text") or (point.payload or {}).get("document", ""),
                    score=float(point.score or 0.0),
                    metadata=point.payload or {},
                )
                for point in filtered
            ],
            used_fallback=self.gemini_provider.is_fallback,
        )
