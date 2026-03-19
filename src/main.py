"""Canonical FastAPI application entrypoint for mAIcro."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.error_handlers import register_exception_handlers
from api.routes import router
from core.config import settings
from core.discord_listener import run_discord_listener
from core.ingestion import ingest_from_discord, run_startup_audit
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

        asyncio.create_task(ingest_from_discord())
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
    docs_url=f"{settings.API_V1_STR}/docs" if settings.EXPOSE_API_DOCS else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.EXPOSE_API_DOCS else None,
    openapi_url=(
        f"{settings.API_V1_STR}/openapi.json" if settings.EXPOSE_API_DOCS else None
    ),
)


app.include_router(router, prefix=settings.API_V1_STR)
register_exception_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
