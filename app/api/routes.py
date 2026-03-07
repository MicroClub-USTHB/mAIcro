"""
mAIcro REST API routes.
"""

from fastapi import APIRouter, HTTPException

from app.api.schemas import AskRequest, AskResponse, IngestFileRequest, IngestResponse
from app.core.config import settings
from app.services.qa_service import AskConfigError, AskError, ask_question

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

    try:
        answer = ask_question(req.question)
    except AskConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AskError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")

    return AskResponse(question=req.question, answer=answer)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_file(req: IngestFileRequest):
    """Ingest documents from a local JSON file."""
    from app.core.ingestion import ingest_from_json

    try:
        count = ingest_from_json(req.path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    return IngestResponse(status="ok", documents_ingested=count)


@router.post("/ingest/discord", response_model=IngestResponse)
async def ingest_discord():
    """Fetch messages from Discord channels and ingest them."""
    from app.core.ingestion import ingest_from_discord

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

    try:
        result = await ingest_from_discord()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Discord ingestion failed: {exc}")

    return IngestResponse(
        status="ok",
        documents_ingested=result["total_documents"],
        details=result["channels"],
    )
