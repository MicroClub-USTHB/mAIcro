"""Canonical FastAPI application entrypoint for mAIcro."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from maicro.api.error_handlers import register_exception_handlers
from maicro.api.routes import router
from maicro.core.config import settings
from maicro.core.ingestion import ingest_from_discord
from maicro.core.logging import configure_logging
from maicro.core.logging import configure_logging


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    if settings.DISCORD_BOT_TOKEN and settings.discord_channel_id_list:
        
        asyncio.create_task(ingest_from_discord(limit_per_channel=200))
    
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

app.include_router(router)
register_exception_handlers(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("maicro.main:app", host="0.0.0.0", port=8000, reload=True)
