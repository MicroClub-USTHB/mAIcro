"""API authentication helpers for sensitive routes."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from core.config import settings


api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


def _get_provided_api_key(request: Request, header_value: str | None) -> str | None:
    if header_value:
        return header_value.strip()

    authorization = request.headers.get("Authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None

    return None


def require_api_key(
    request: Request,
    header_value: str | None = Security(api_key_header),
) -> None:
    """Protect sensitive endpoints with a shared API key."""
    if not settings.API_AUTH_ENABLED:
        return

    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API authentication is enabled but API_KEY is not configured on the server."
            ),
        )

    provided_key = _get_provided_api_key(request, header_value)
    if not provided_key or not hmac.compare_digest(provided_key, settings.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
