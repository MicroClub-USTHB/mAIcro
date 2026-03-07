import json
import os
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from app.core.llm_provider import get_embeddings
from app.core.config import settings

def ingest_data(file_path: str):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    with open(file_path, "r") as f:
        data = json.load(f)

    documents = []
    for item in data:
        content = f"{item['title']}\n{item['content']}"
        metadata = {"date": item.get("date", ""), "title": item["title"]}
        documents.append(Document(page_content=content, metadata=metadata))

    print(f"Ingesting {len(documents)} documents into Qdrant (local mode)...")
    
    # Simple direct ingestion using the class method
    QdrantVectorStore.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        path="local_qdrant",
        collection_name=settings.COLLECTION_NAME,
    )
    print("Ingestion complete!")

if __name__ == "__main__":
    if not settings.GOOGLE_API_KEY:
        print(
            "Error: GOOGLE_API_KEY not found in .env. "
            "Ingestion embeddings currently use Google."
        )
        os._exit(1)
    ingest_data("data/announcements.json")
