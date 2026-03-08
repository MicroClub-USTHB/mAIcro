from pydantic_settings import BaseSettings, SettingsConfigDict
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
    MODEL_NAME: Optional[str] = None
    GOOGLE_MODEL_NAME: str = "gemini-2.0-flash-lite"

    # Discord ingestion
    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_CHANNEL_IDS: Optional[str] = None

    # Vector Store
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: Optional[str] = None
    COLLECTION_NAME: str = "microclub_knowledge"

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

        return [cid.strip() for cid in self.DISCORD_CHANNEL_IDS.split(",") if cid.strip()]

settings = Settings()
