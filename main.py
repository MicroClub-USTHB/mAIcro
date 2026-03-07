"""
mAIcro — AI-powered knowledge service.

Run with:
    uvicorn main:app --reload
    # or
    uv run uvicorn main:app --reload
"""

from fastapi import FastAPI
from app.core.config import settings
from app.api.routes import router


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        f"AI knowledge service for {settings.ORG_NAME}. "
        "Ingest data from Discord or JSON files, then ask questions."
    ),
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
