"""Compatibility wrapper for the canonical entrypoint in app.main."""

from app.main import app


if __name__ == "__main__":
    import uvicorn

    # Keep historical root-level startup working for existing docs/scripts.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
