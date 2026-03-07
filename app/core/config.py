from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Organization Settings (Reusable for any club/org)
    ORG_NAME: str = "Community"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"
    CORE_RULES: Optional[List[str]] = None
    # AI Settings
    GOOGLE_API_KEY: Optional[str] = None
    MODEL_NAME: str = "gemini-1.5-flash"

    # Vector Store
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    COLLECTION_NAME: str = "maicro_knowledge"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
