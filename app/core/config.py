
"""
Central configuration for the entire app.

All settings are loaded from environment variables or a .env file.
Fields marked ClassVar are internal constants — not loaded from env.
Pydantic validates everything on startup, so bad config = immediate crash (not silent bugs).
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, ClassVar, Dict
from qdrant_client.http import models as qdrant_models

# Allowed distance metrics for Qdrant. Used to validate VECTORSTORE_DISTANCE.
VALID_DISTANCES = {"COSINE", "EUCLID", "DOT", "MANHATTAN"}

class Settings(BaseSettings):

    # ── General ──────────────────────────────────────────────────────────
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # ── Organization info ────────────────────────────────────────────────
    ORG_NAME: str = "Community"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"

    # ── Gemini embedding API ─────────────────────────────────────────────
    GEMINI_API_KEY: str                                  # Required — no default
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"   # Which Gemini model to use
    EMBEDDING_DIM: int = 768                             # Output vector size
    EMBEDDING_MAX_RETRIES: int = 3                       # How many times to retry a failed API call
    EMBEDDING_RETRY_BASE_DELAY: float = 1.0              # Starting delay (seconds) — doubles each retry

    # ── Qdrant vector store ──────────────────────────────────────────────
    VECTORSTORE_PATH: str             # Required — local path to Qdrant DB
    VECTORSTORE_COLLECTION: str       # Required — name of the Qdrant collection
    VECTORSTORE_BATCH_SIZE: int = 64  # How many documents to upload per batch
    VECTORSTORE_MAX_RETRIES: int = 3  # Max retries for upload failures
    VECTORSTORE_DISTANCE: str = "COSINE"  # Similarity metric (COSINE, EUCLID, DOT, MANHATTAN)

    # ── Database (reserved for future use) ───────────────────────────────
    DATABASE_URL: Optional[str] = None

    # ── Validators ───────────────────────────────────────────────────────
    # Runs at startup when Settings() is created. Rejects invalid values before the app starts.

    @field_validator("VECTORSTORE_DISTANCE")
    @classmethod
    def _validate_distance(cls, v: str) -> str:
        """Normalize to uppercase and reject unknown metrics."""
        upper = v.upper()
        if upper not in VALID_DISTANCES:
            raise ValueError(
                f"Invalid VECTORSTORE_DISTANCE: {v!r}. Must be one of {VALID_DISTANCES}"
            )
        return upper

    # ── Internal constants (not loaded from .env) ────────────────────────
    # ClassVar fields are NOT read from environment — they're code-level constants.

    # Which schema version new documents should use (e.g. "v1", "v2", "v3")
    CURRENT_SCHEMA_VERSION: ClassVar[str] = "v2"

    # Gemini uses different task types for documents vs queries (improves retrieval quality)
    EMBEDDING_TASK_TYPES: ClassVar[Dict[str, str]] = {
        'document': 'RETRIEVAL_DOCUMENT',
        'query': 'RETRIEVAL_QUERY',
    }

    # Fields to index in Qdrant for fast filtering during search
    VECTORSTORE_PAYLOAD_INDEXES: ClassVar[Dict[str, qdrant_models.PayloadSchemaType]] = {
        "channel": qdrant_models.PayloadSchemaType.KEYWORD,
        "author": qdrant_models.PayloadSchemaType.KEYWORD,
        "timestamp": qdrant_models.PayloadSchemaType.DATETIME,
        "_schema_version": qdrant_models.PayloadSchemaType.KEYWORD,
    }

    model_config = {
        "case_sensitive": True,
        "env_file": ".env"
    }

# Single global instance — import `settings` anywhere to access config
settings = Settings()
