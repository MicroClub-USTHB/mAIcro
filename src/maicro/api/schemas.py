"""API request/response models."""

from typing import Optional

from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    answer: str


class IngestResponse(BaseModel):
    status: str
    documents_ingested: int
    details: Optional[dict] = None
