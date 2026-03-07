from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    channel: Optional[str] = None
    author: Optional[str] = None
    timestamp: Optional[datetime] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    id: str
    text: str
    metadata: DocumentMetadata