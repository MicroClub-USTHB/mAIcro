import os

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

class Settings(BaseSettings):
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Organization Settings (Reusable for any club/org)
    ORG_NAME: str = "Community"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"
    
    # AI Settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "your-gemini-api-key")
    
    
    
    LLM_PROVIDER: str = "gemini"
    # use a fully‑qualified model name that exists in the API (see genai.list_models())
    # the old "gemini-1"/"gemini-1.5-flash" are not available in v1beta
    LLM_MODEL: str = Field("gemini-1.5-flash", env="LLM_MODEL")
    
    # Database
    DATABASE_URL: Optional[str] = None

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
