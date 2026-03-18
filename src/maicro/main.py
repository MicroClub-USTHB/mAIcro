"""Canonical FastAPI application entrypoint for mAIcro."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from maicro.api.error_handlers import register_exception_handlers
from maicro.api.routes import router
from maicro.core.config import settings
from maicro.core.discord_listener import run_discord_listener
from maicro.core.ingestion import ingest_from_discord, run_startup_audit
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DISCORD_BOT_TOKEN and settings.discord_channel_id_list:
        audit_task = asyncio.create_task(
            run_startup_audit(settings.discord_channel_id_list, window=200)
        )
        try:
            audit_summary = await audit_task
            logger.info("[startup] Audit completed: %s", audit_summary)
        except Exception as exc:
            logger.error("[startup] Audit failed: %s", exc)

        asyncio.create_task(ingest_from_discord(limit_per_channel=None))
        asyncio.create_task(
            run_discord_listener(
                bot_token=settings.DISCORD_BOT_TOKEN,
                channel_ids=settings.discord_channel_id_list,
            )
        )

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    version=settings.VERSION,
    description=(
        f"AI knowledge service for {settings.ORG_NAME}. "
        "Ingest data from Discord or JSON files, then ask questions."
    ),
)

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


app.include_router(router)
register_exception_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("maicro.main:app", host="0.0.0.0", port=8000, reload=True)
