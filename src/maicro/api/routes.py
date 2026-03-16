"""
mAIcro REST API routes.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from maicro.api.schemas import AskRequest, AskResponse, IngestResponse
from maicro.core.config import settings
from maicro.services.qa_service import ask_question

router = APIRouter(prefix=settings.API_V1_STR)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "org": settings.ORG_NAME,
        "llm_provider": settings.LLM_PROVIDER,
    }


@router.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    """Answer a question using the RAG chain."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, ask_question, req.question)

    return AskResponse(question=req.question, answer=answer)


@router.post("/ingest/discord", response_model=IngestResponse)
async def ingest_discord():
    """Fetch messages from Discord channels and ingest them."""
    from maicro.core.ingestion import ingest_from_discord

    if not settings.DISCORD_BOT_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="DISCORD_BOT_TOKEN not configured. Set it in your .env file.",
        )
    if not settings.discord_channel_id_list:
        raise HTTPException(
            status_code=400,
            detail="DISCORD_CHANNEL_IDS not configured. Set it in your .env file.",
        )

    result = await ingest_from_discord()

    has_errors = bool(result.get("errors"))

    return IngestResponse(
        status="partial" if has_errors else "ok",
        documents_ingested=result["total_documents"],
        details={
            "channels": result.get("channels", {}),
            "errors": result.get("errors", {}),
        },
    )
