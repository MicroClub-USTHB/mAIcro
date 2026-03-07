from fastapi import FastAPI
from app.api.v1 import api_router
from app.api.routes.health import router as health_router

app = FastAPI(
    title="mAIcro",
    description="Community Intelligence Service - Reusable AI Infrastructure",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")
