"""
API Dependencies — SIA Backend
Centralized FastAPI dependency injection: DB pool, settings, auth.
"""
from typing import Annotated
from fastapi import Depends
from backend.core.config import Settings, get_settings
from backend.core.security import verify_api_key
from backend.services.db_executor import get_pool


async def get_db():
    """Dependency: return the asyncpg connection pool."""
    pool = await get_pool()
    return pool


# Type aliases for cleaner route signatures
SettingsDep = Annotated[Settings, Depends(get_settings)]
AuthDep = Annotated[str, Depends(verify_api_key)]
