# ingest.py
# Endpoint for ingesting Discord messages/events

from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/ingest")
def ingest_event(request: Request):
    """
    Accepts Discord event payload (new/edit/delete message) for monitored channels.
    Classifies channel/author, extracts facts/events, upserts to DB, enqueues embedding.
    """
    # ...implementation...
    return {"status": "ok"}
