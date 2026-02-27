from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Organization Settings (Reusable for any club/org)
    ORG_NAME: str = "Community"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"
    
    # AI Settings
    GEMINI_API_KEY: str
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-1"
    
    # Database
    DATABASE_URL: Optional[str] = None

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
