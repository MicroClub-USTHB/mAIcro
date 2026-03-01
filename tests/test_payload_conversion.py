from datetime import datetime

from app.core.vector_store import QdrantVectorStore
from app.schemas.documents import Document, DocumentMetadata


def test_document_to_payload_and_back_preserves_data_without_mutation():
    metadata = DocumentMetadata(
        channel="general",
        author="alice",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        attributes={"topic": "ai"},
    )
    doc = Document(id="doc-1", text="Hello world", metadata=metadata)

    payload = QdrantVectorStore.document_to_payload(doc, schema_version="1")

    # Original metadata should remain unchanged
    assert metadata.attributes == {"topic": "ai"}

    # Payload should contain serialized fields
    assert payload["text"] == "Hello world"
    assert payload["document"] == "Hello world"
    assert payload["_schema_version"] == "1"
    assert payload["channel"] == "general"
    assert payload["author"] == "alice"
    assert payload["attributes"] == {"topic": "ai"}
    assert isinstance(payload["timestamp"], str)

    # Convert back to Document
    restored = QdrantVectorStore.payload_to_document("doc-1", payload)
    assert restored.id == "doc-1"
    assert restored.text == "Hello world"
    assert restored.metadata.channel == "general"
    assert restored.metadata.author == "alice"
    assert restored.metadata.attributes == {"topic": "ai"}
    # Pydantic parses timestamp string to datetime
    assert isinstance(restored.metadata.timestamp, datetime)