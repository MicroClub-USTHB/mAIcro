
import pytest
from app.core.vector_store import QdrantVectorStore
from app.schemas.documents import Document, DocumentMetadata
import uuid

def test_vector_store_end_to_end():
    store = QdrantVectorStore()
    # Use valid UUIDs for document IDs
    docs = [
        Document(id=str(uuid.uuid4()), text="The quick brown fox jumps over the lazy dog.", metadata=DocumentMetadata(channel="test", author="user", timestamp=None, attributes={})),
        Document(id=str(uuid.uuid4()), text="A fast brown fox leaps over a sleepy dog.", metadata=DocumentMetadata(channel="test", author="user", timestamp=None, attributes={})),
        Document(id=str(uuid.uuid4()), text="Completely unrelated text about the ocean.", metadata=DocumentMetadata(channel="test", author="user", timestamp=None, attributes={})),
    ]
    store.add_document_models(docs)
    # Test similarity search for a relevant query
    results = store.similarity_search("quick fox", n_results=2)
    assert len(results) == 2
    texts = [r.payload.get("text") for r in results]
    assert any("fox" in t for t in texts)
    # Test similarity search for an unrelated query
    unrelated = store.similarity_search("ocean", n_results=1)
    assert len(unrelated) == 1
    assert "ocean" in unrelated[0].payload.get("text")
    # Test metadata retrieval
    for r in results:
        assert r.payload.get("channel") == "test"
        assert r.payload.get("author") == "user"
