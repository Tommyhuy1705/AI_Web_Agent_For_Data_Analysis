"""
Database Executor Service
Tương tác với Supabase PostgreSQL qua asyncpg.
Cung cấp connection pool và các hàm thực thi SQL an toàn.
"""

import os
import re
import logging
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)

DEFAULT_MAX_ROWS = int(os.getenv("SQL_PROXY_MAX_ROWS", "1000"))
MAX_SQL_LENGTH = int(os.getenv("SQL_PROXY_MAX_SQL_LENGTH", "20000"))

# Supabase connection string
DATABASE_URL = os.getenv(
    "SUPABASE_DATABASE_URL",
    "postgresql://postgres:your_password@db.your_project.supabase.co:5432/postgres"
)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Lấy hoặc tạo connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("Database connection pool created successfully")
    return _pool


async def close_pool():
    """Đóng connection pool."""
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")


def validate_sql_query(sql: str) -> bool:
    """
    Validate SQL query - chỉ cho phép SELECT statements.
    Ngăn chặn SQL injection và các câu lệnh nguy hiểm.
    """
    cleaned = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip().upper()

    if not cleaned:
        return False

    if len(cleaned) > MAX_SQL_LENGTH:
        return False

    # Chặn multi-statement (ngoại trừ dấu ; ở cuối)
    compact = cleaned.rstrip(";").strip()
    if ";" in compact:
        return False

    # Chỉ cho phép truy vấn read-only: SELECT hoặc WITH ... SELECT
    if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
        return False

    # Từ chối các keyword nguy hiểm
    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
        "INTO", "SET", "COPY",
    ]

    for keyword in dangerous_keywords:
        pattern = rf'\b{keyword}\b'
        if re.search(pattern, cleaned):
            return False

    expensive_patterns = [
        r"\bCROSS\s+JOIN\b",
        r"\bNATURAL\s+JOIN\b",
        r"\bGENERATE_SERIES\s*\(",
        r"\bPG_SLEEP\s*\(",
    ]
    for pattern in expensive_patterns:
        if re.search(pattern, cleaned):
            return False

    return True


def normalize_sql(sql: str) -> str:
    """Normalize SQL whitespace and remove trailing semicolons."""
    normalized = sql.strip().rstrip(";").strip()
    return normalized


def ensure_default_limit(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Append LIMIT if caller did not provide one in outer query."""
    normalized = normalize_sql(sql)
    if re.search(r"\bLIMIT\s+\d+\b", normalized, flags=re.IGNORECASE):
        return normalized
    return f"{normalized} LIMIT {max_rows}"


def prepare_safe_select_query(sql: str, max_rows: int = DEFAULT_MAX_ROWS) -> str:
    """Validate and enforce safe defaults before SQL execution."""
    if not validate_sql_query(sql):
        raise ValueError("Only safe read-only SELECT queries are allowed")
    return ensure_default_limit(sql, max_rows=max_rows)


async def execute_safe_query(
    sql: str,
    params: Optional[List[Any]] = None,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    Thực thi SQL query an toàn (chỉ SELECT).
    Trả về danh sách dict (mảng JSON).
    """
    safe_sql = prepare_safe_select_query(sql)

    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            if params:
                rows = await conn.fetch(safe_sql, *params, timeout=timeout)
            else:
                rows = await conn.fetch(safe_sql, timeout=timeout)

            # Convert Record objects to dicts
            result = [dict(row) for row in rows]
            logger.info(f"Query executed successfully, returned {len(result)} rows")
            return result

        except asyncpg.PostgresError as e:
            logger.error(f"Database query error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}")
            raise


async def execute_write_query(
    sql: str,
    params: Optional[List[Any]] = None,
    timeout: int = 30
) -> str:
    """
    Thực thi SQL write query (INSERT, UPDATE, UPSERT).
    Chỉ dùng cho internal services (alarm_monitor, etc.).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            if params:
                result = await conn.execute(sql, *params, timeout=timeout)
            else:
                result = await conn.execute(sql, timeout=timeout)
            logger.info(f"Write query executed: {result}")
            return result
        except asyncpg.PostgresError as e:
            logger.error(f"Database write error: {e}")
            raise


async def fetch_one(
    sql: str,
    params: Optional[List[Any]] = None,
    timeout: int = 30
) -> Optional[Dict[str, Any]]:
    """Fetch một row duy nhất."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            if params:
                row = await conn.fetchrow(sql, *params, timeout=timeout)
            else:
                row = await conn.fetchrow(sql, timeout=timeout)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Fetch one error: {e}")
            raise


async def health_check() -> Dict[str, Any]:
    """Kiểm tra kết nối database."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT NOW() as current_time, version() as pg_version")
            return {
                "status": "healthy",
                "current_time": str(result["current_time"]),
                "pg_version": result["pg_version"][:50],
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
