from fastapi import APIRouter, Depends

from app.api.dependencies import get_query_service
from app.models.schemas import ChatRequest, ChatResponse
from app.services.query_service import QueryService

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    query_service: QueryService = Depends(get_query_service),
) -> ChatResponse:
    return query_service.chat(payload)
