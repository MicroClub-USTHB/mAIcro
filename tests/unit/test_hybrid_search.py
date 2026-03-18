"""Test hybrid search for specific Discord Message ID."""

import pytest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from core.hybrid_search import hybrid_search
from core.config import settings


def test_hybrid_search_returns_specific_message_as_top_hit():
    """Test that searching for a specific Discord Message ID returns correct result as top hit."""
    
    # Sample documents with known message IDs
    docs = [
        Document(
            page_content="[user1] Hello world",
            metadata={
                "source": "discord",
                "channel_id": "123",
                "message_id": "456",
                "author": "user1",
                "timestamp": "2026-03-18T10:00:00"
            }
        ),
        Document(
            page_content="[user2] Another message",
            metadata={
                "source": "discord",
                "channel_id": "123",
                "message_id": "789",
                "author": "user2", 
                "timestamp": "2026-03-18T10:01:00"
            }
        ),
        Document(
            page_content="[user3] Third message with ID-123456 in content",
            metadata={
                "source": "discord",
                "channel_id": "123",
                "message_id": "999",
                "author": "user3",
                "timestamp": "2026-03-18T10:02:00"
            }
        ),
    ]
    
    # Mock the Qdrant client to return our test documents
    mock_hit1 = MagicMock()
    mock_hit1.payload = {
        "page_content": "[user1] Hello world",
        "metadata": {
            "source": "discord",
            "channel_id": "123",
            "message_id": "456",
            "author": "user1",
            "timestamp": "2026-03-18T10:00:00"
        }
    }
    
    mock_hit2 = MagicMock()
    mock_hit2.payload = {
        "page_content": "[user2] Another message",
        "metadata": {
            "source": "discord",
            "channel_id": "123",
            "message_id": "789",
            "author": "user2",
            "timestamp": "2026-03-18T10:01:00"
        }
    }
    
    mock_hit3 = MagicMock()
    mock_hit3.payload = {
        "page_content": "[user3] Third message with ID-123456 in content",
        "metadata": {
            "source": "discord",
            "channel_id": "123",
            "message_id": "999",
            "author": "user3",
            "timestamp": "2026-03-18T10:02:00"
        }
    }
    
    # Mock query_points response - returns an object with .points attribute
    mock_result = MagicMock()
    mock_result.points = [mock_hit1, mock_hit2, mock_hit3]
    
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_result
    
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.1] * 3072
    
    with patch('core.hybrid_search._get_qdrant_client', return_value=mock_client):
        with patch('core.hybrid_search.get_embeddings', return_value=mock_embeddings):
            # Search for message with ID 456 - BM25 will search metadata.message_id
            results = hybrid_search(query="456", k=3)
    
    # Verify the top result is the document with message_id 456
    assert len(results) > 0
    assert results[0].metadata["message_id"] == "456"


def test_hybrid_search_with_keyword_match():
    """Test that keyword search finds message with specific text."""
    
    mock_hit = MagicMock()
    mock_hit.payload = {
        "page_content": "[user3] Third message with ID-123456 in content",
        "metadata": {
            "source": "discord",
            "channel_id": "123",
            "message_id": "999",
            "author": "user3",
            "timestamp": "2026-03-18T10:02:00"
        }
    }
    
    # Mock query_points response
    mock_result = MagicMock()
    mock_result.points = [mock_hit]
    
    mock_client = MagicMock()
    mock_client.query_points.return_value = mock_result
    
    mock_embeddings = MagicMock()
    mock_embeddings.embed_query.return_value = [0.1] * 3072
    
    with patch('core.hybrid_search._get_qdrant_client', return_value=mock_client):
        with patch('core.hybrid_search.get_embeddings', return_value=mock_embeddings):
            # Search for specific text
            results = hybrid_search(query="ID-123456", k=1)
    
    assert len(results) > 0
    assert "ID-123456" in results[0].page_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
