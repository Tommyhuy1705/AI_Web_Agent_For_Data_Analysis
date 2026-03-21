"""
Security utilities — SIA Backend
Provides API key authentication dependency for protected endpoints.
"""
import os
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Dependency: verify X-API-Key header for protected routes.
    If INTERNAL_API_KEY is not set, all requests are allowed (dev mode).
    """
    if not _INTERNAL_API_KEY:
        return "dev-mode"
    if api_key != _INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
