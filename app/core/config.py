from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    ORG_NAME: str = "MicroClub"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"
    CORE_RULES: Optional[List[str]] = None

    # AI Settings
    LLM_PROVIDER: str = "google"
    GOOGLE_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    MODEL_NAME: Optional[str] = None
    GOOGLE_MODEL_NAME: str = "gemini-2.0-flash-lite"
    ANTHROPIC_MODEL_NAME: str = "claude-3-5-haiku-latest"

    # Vector Store
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    COLLECTION_NAME: str = "microclub_knowledge"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
