"""Canonical FastAPI application entrypoint for mAIcro."""

from fastapi import FastAPI

from app.api.error_handlers import register_exception_handlers
from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging


configure_logging()


app = FastAPI(
    title=settings.PROJECT_NAME,
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

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
