
from pydantic_settings import BaseSettings
from typing import Optional, ClassVar, Dict

class Settings(BaseSettings):
    
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Organization Settings (Reusable for any club/org)
    ORG_NAME: str = "Community"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"
    

    # AI Settings
    GEMINI_API_KEY: Optional[str] = None
    MODEL_NAME: Optional[str] = None
    EMBEDDING_MODEL_NAME: str = "gemini-embedding-001"
    
    # Embedding settings
    EMBEDDING_DIM: int = 768
    EMBEDDING_TASK_TYPES: ClassVar[Dict[str, str]] = {'document': 'RETRIEVAL_DOCUMENT', 'query': 'RETRIEVAL_QUERY'}

    # Vector store
    VECTORSTORE_PATH: str  # required, no default
    VECTORSTORE_COLLECTION: str  # required, no default

    # Database
    DATABASE_URL: Optional[str] = None

    model_config = {
        "case_sensitive": True,
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
