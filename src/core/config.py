from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "mAIcro"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    API_AUTH_ENABLED: bool = True
    API_KEY: Optional[str] = None
    API_KEY_HEADER: str = "X-API-Key"
    EXPOSE_API_DOCS: bool = False

    ORG_NAME: str = "MicroClub"
    ORG_DESCRIPTION: Optional[str] = "A generic organization using mAIcro"
    CORE_RULES: Optional[List[str]] = None

    LLM_PROVIDER: str = "google"
    SECONDARY_LLM_PROVIDER: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    SECONDARY_GEMINI_API_KEY: Optional[str] = None
    MODEL_NAME: Optional[str] = None
    SECONDARY_MODEL_NAME: Optional[str] = None
    GOOGLE_MODEL_NAME: str = "gemini-2.5-flash"
    LLM_FALLBACK_ENABLED: bool = False
    LLM_MAX_PRIMARY_ATTEMPTS: int = 3
    LLM_BACKOFF_BASE_DELAY_SECONDS: float = 1.0
    LLM_BACKOFF_MAX_DELAY_SECONDS: float = 8.0

    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_CHANNEL_IDS: Optional[str] = None

    QDRANT_URL: Optional[str] = None
    QDRANT_API_KEY: Optional[str] = None
    COLLECTION_NAME: str = "microclub_knowledge"
    
    
    HYBRID_SEARCH_ALPHA: float = 0.7  
    HYBRID_SEARCH_RRF_K: int = 60   

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        extra="ignore",
    )

    @property
    def discord_channel_id_list(self) -> List[str]:
        """Parse comma-separated channel IDs from DISCORD_CHANNEL_IDS."""
        if not self.DISCORD_CHANNEL_IDS:
            return []

        return [
            cid.strip() for cid in self.DISCORD_CHANNEL_IDS.split(",") if cid.strip()
        ]


settings = Settings()
