"""API key authentication dependency.

In development mode (ENVIRONMENT=development) with no keys configured,
auth is bypassed and requests are treated as anonymous.

In production, a valid X-API-Key header is required.
"""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from odyssey_rag.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(api_key_header),
) -> str:
    """Verify the API key from the X-API-Key header.

    Returns:
        The validated API key string, or "dev-anonymous" in permissive dev mode.

    Raises:
        HTTPException 401: If no valid key is provided in non-permissive mode.
    """
    settings = get_settings()
    valid_keys = settings.api_keys

    # Development mode with no keys configured — auth is optional
    if settings.environment == "development" and not valid_keys:
        return "dev-anonymous"

    if not api_key or api_key not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
