from app.core.embeddings import EmbeddingService
from app.services.ai import GeminiProvider
from app.core.vector_store import InMemoryVectorStore
from app.models.schemas import ChatRequest, ChatResponse, SourceChunk


class QueryService:
    def __init__(self,vector_store: InMemoryVectorStore,embedding_service: EmbeddingService,gemini_provider: GeminiProvider,) -> None:
      self.vector_store = vector_store
      self.embedding_service = embedding_service
      self.gemini_provider = gemini_provider

    def chat(self, payload: ChatRequest) -> ChatResponse:
        query_embedding = self.embedding_service.embed_text(payload.query)
        retrieved = self.vector_store.similarity_search(
                        query_embedding=query_embedding,
                        query_text=payload.query,
                        top_k=payload.top_k,
                        min_score=payload.min_score,
                    )
        # still need to change the provider to return sources and fallback status and get the retrieved chunks in the params
        answer = self.gemini_provider.generate(query=payload.query, retrieved=retrieved,history=payload.history)

        return ChatResponse(
            answer=answer,
            sources=[SourceChunk(**item) for item in retrieved],
            used_fallback=self.gemini_provider.is_fallback,
        )
