from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, description="User question")
    n_results: int = Field(default=5, ge=1, le=20)
    history: List[ChatMessage] = Field(default_factory=list)


class SourceChunk(BaseModel):
    id: str
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk] = Field(default_factory=list)
    used_fallback: bool = False


