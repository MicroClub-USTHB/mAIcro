from fastapi import FastAPI
from app.api.v1 import api_router

app = FastAPI(
    title="mAIcro",
    description="Community Intelligence Service - Reusable AI Infrastructure",
    version="0.1.0",
)

@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "version": "0.1.0"}

# app.include_router(api_router, prefix="/api/v1")
