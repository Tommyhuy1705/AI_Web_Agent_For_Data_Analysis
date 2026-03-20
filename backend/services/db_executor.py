"""
Database Executor Service
Tương tác với Supabase PostgreSQL qua REST API (PostgREST) + asyncpg fallback.
Cung cấp connection pool và các hàm thực thi SQL an toàn.

Strategy:
1. Primary: Supabase REST API (PostgREST) - works through HTTPS, no direct DB connection needed
2. Fallback: asyncpg direct connection (if SUPABASE_DATABASE_URL is provided)
"""

import json
import os
import re
import logging
from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal

import httpx

logger = logging.getLogger(__name__)

# Supabase REST API configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Use service role key for full access, fallback to anon key
_api_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY

# asyncpg fallback
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL", "")

# Global asyncpg pool (if available)
_pool = None


def _get_headers(schema: str = "public") -> dict:
    """Get headers for Supabase REST API."""
    return {
        "apikey": _api_key,
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Profile": schema,
        "Content-Profile": schema,
        "Prefer": "return=representation",
    }


async def get_pool():
    """Lấy hoặc tạo asyncpg connection pool (fallback)."""
    global _pool
    if not SUPABASE_DATABASE_URL or SUPABASE_DATABASE_URL.startswith("postgresql://postgres:your_password"):
        logger.info("No valid SUPABASE_DATABASE_URL, using REST API mode")
        return None

    try:
        import asyncpg
        if _pool is None or _pool._closed:
            _pool = await asyncpg.create_pool(
                SUPABASE_DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=30,
            )
            logger.info("Database connection pool created successfully (asyncpg)")
        return _pool
    except Exception as e:
        logger.warning(f"asyncpg pool creation failed: {e}")
        return None


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

    if not cleaned.startswith("SELECT"):
        return False

    dangerous_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
        "SET", "COPY",
    ]

    for keyword in dangerous_keywords:
        pattern = rf'\b{keyword}\b'
        if re.search(pattern, cleaned):
            return False

    return True


def _serialize_value(val: Any) -> Any:
    """Serialize special types for JSON."""
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def _serialize_row(row: dict) -> dict:
    """Serialize a row dict."""
    return {k: _serialize_value(v) for k, v in row.items()}


async def _execute_via_rpc(sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute SQL via Supabase RPC function 'exec_sql'.
    This requires the exec_sql function to be created in Supabase.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            json={"query": sql},
            headers=_get_headers("public"),
        )

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            return [data] if data else []
        else:
            raise Exception(f"RPC exec_sql error {response.status_code}: {response.text}")


async def _execute_via_postgrest(table: str, schema: str = "public",
                                  select: str = "*", filters: dict = None,
                                  limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Execute query via PostgREST (Supabase REST API).
    """
    params = {"select": select, "limit": str(limit)}
    if filters:
        params.update(filters)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params=params,
            headers=_get_headers(schema),
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"PostgREST error {response.status_code}: {response.text}")


async def _execute_via_asyncpg(sql: str, params: Optional[List[Any]] = None,
                                timeout: int = 30) -> List[Dict[str, Any]]:
    """Execute SQL via asyncpg direct connection."""
    pool = await get_pool()
    if pool is None:
        raise Exception("No asyncpg pool available")

    async with pool.acquire() as conn:
        if params:
            rows = await conn.fetch(sql, *params, timeout=timeout)
        else:
            rows = await conn.fetch(sql, timeout=timeout)
        return [_serialize_row(dict(row)) for row in rows]


async def execute_safe_query(
    sql: str,
    params: Optional[List[Any]] = None,
    timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    Thực thi SQL query an toàn (chỉ SELECT).
    Trả về danh sách dict (mảng JSON).

    Strategy:
    1. Try asyncpg (if pool available)
    2. Try Supabase RPC exec_sql
    3. Try PostgREST (parse SQL to table query)
    """
    if not validate_sql_query(sql):
        raise ValueError("Only SELECT queries are allowed for security reasons")

    errors = []

    # Strategy 1: asyncpg direct
    if SUPABASE_DATABASE_URL and not SUPABASE_DATABASE_URL.startswith("postgresql://postgres:your_password"):
        try:
            result = await _execute_via_asyncpg(sql, params, timeout)
            logger.info(f"Query via asyncpg: {len(result)} rows")
            return result
        except Exception as e:
            errors.append(f"asyncpg: {e}")
            logger.debug(f"asyncpg failed: {e}")

    # Strategy 2: Supabase RPC
    if SUPABASE_URL and _api_key:
        try:
            result = await _execute_via_rpc(sql, params)
            logger.info(f"Query via RPC: {len(result)} rows")
            return result
        except Exception as e:
            errors.append(f"RPC: {e}")
            logger.debug(f"RPC failed: {e}")

    # Strategy 3: PostgREST (parse simple queries)
    if SUPABASE_URL and _api_key:
        try:
            result = await _parse_and_execute_postgrest(sql)
            if result is not None:
                logger.info(f"Query via PostgREST: {len(result)} rows")
                return result
        except Exception as e:
            errors.append(f"PostgREST: {e}")
            logger.debug(f"PostgREST failed: {e}")

    error_msg = "; ".join(errors)
    raise Exception(f"All query strategies failed: {error_msg}")


async def _parse_and_execute_postgrest(sql: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse simple SELECT SQL and convert to PostgREST query.
    Supports: SELECT columns FROM [schema.]table [WHERE ...] [ORDER BY ...] [LIMIT n]
    """
    sql_clean = sql.strip().rstrip(";")

    # Extract table name (handle schema.table format)
    from_match = re.search(r'\bFROM\s+([\w.]+)', sql_clean, re.IGNORECASE)
    if not from_match:
        return None

    full_table = from_match.group(1)
    if "." in full_table:
        schema, table = full_table.rsplit(".", 1)
    else:
        schema, table = "public", full_table

    # Extract select columns
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_clean, re.IGNORECASE | re.DOTALL)
    select_cols = "*"
    if select_match:
        cols = select_match.group(1).strip()
        if cols != "*":
            select_cols = cols

    # Extract limit
    limit = 1000
    limit_match = re.search(r'LIMIT\s+(\d+)', sql_clean, re.IGNORECASE)
    if limit_match:
        limit = int(limit_match.group(1))

    # Extract order by
    order_params = {}
    order_match = re.search(r'ORDER\s+BY\s+([\w.]+)\s*(ASC|DESC)?', sql_clean, re.IGNORECASE)
    if order_match:
        order_col = order_match.group(1).split(".")[-1]
        order_dir = order_match.group(2) or "ASC"
        order_params["order"] = f"{order_col}.{order_dir.lower()}"

    params = {"select": select_cols, "limit": str(limit)}
    params.update(order_params)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/{table}",
            params=params,
            headers=_get_headers(schema),
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 406:
            # Schema not exposed, try public
            if schema != "public":
                response2 = await client.get(
                    f"{SUPABASE_URL}/rest/v1/{table}",
                    params=params,
                    headers=_get_headers("public"),
                )
                if response2.status_code == 200:
                    return response2.json()
            raise Exception(f"PostgREST: Schema '{schema}' not exposed. Status: {response.status_code}")
        else:
            raise Exception(f"PostgREST error {response.status_code}: {response.text[:200]}")


async def execute_write_query(
    sql: str,
    params: Optional[List[Any]] = None,
    timeout: int = 30
) -> str:
    """
    Thực thi SQL write query (INSERT, UPDATE, UPSERT).
    Chỉ dùng cho internal services (alarm_monitor, etc.).
    """
    # Try asyncpg first
    pool = await get_pool()
    if pool:
        async with pool.acquire() as conn:
            if params:
                result = await conn.execute(sql, *params, timeout=timeout)
            else:
                result = await conn.execute(sql, timeout=timeout)
            logger.info(f"Write query executed (asyncpg): {result}")
            return result

    # Try RPC
    if SUPABASE_URL and _api_key:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    json={"query": sql},
                    headers=_get_headers("public"),
                )
                if response.status_code == 200:
                    return "OK"
                else:
                    logger.warning(f"RPC write failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"RPC write failed: {e}")

    # Fallback: parse and use PostgREST for simple operations
    logger.warning("Write query fallback: operation may not be fully supported via REST API")
    return "SKIPPED"


async def fetch_one(
    sql: str,
    params: Optional[List[Any]] = None,
    timeout: int = 30
) -> Optional[Dict[str, Any]]:
    """Fetch một row duy nhất."""
    results = await execute_safe_query(sql, params, timeout)
    return results[0] if results else None


async def insert_via_rest(
    table: str,
    data: dict,
    schema: str = "public"
) -> dict:
    """Insert data via Supabase REST API."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            json=data,
            headers=_get_headers(schema),
        )
        if response.status_code in (200, 201):
            result = response.json()
            return result[0] if isinstance(result, list) and result else result
        else:
            raise Exception(f"Insert error {response.status_code}: {response.text[:200]}")


async def upsert_via_rest(
    table: str,
    data: dict,
    schema: str = "public",
    on_conflict: str = ""
) -> dict:
    """Upsert data via Supabase REST API."""
    headers = _get_headers(schema)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            json=data,
            headers=headers,
        )
        if response.status_code in (200, 201):
            result = response.json()
            return result[0] if isinstance(result, list) and result else result
        else:
            raise Exception(f"Upsert error {response.status_code}: {response.text[:200]}")


async def health_check() -> Dict[str, Any]:
    """Kiểm tra kết nối database."""
    # Try REST API
    if SUPABASE_URL and _api_key:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{SUPABASE_URL}/rest/v1/",
                    headers=_get_headers("public"),
                )
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "mode": "rest_api",
                        "supabase_url": SUPABASE_URL,
                    }
        except Exception as e:
            pass

    # Try asyncpg
    try:
        pool = await get_pool()
        if pool:
            async with pool.acquire() as conn:
                result = await conn.fetchrow("SELECT NOW() as current_time, version() as pg_version")
                return {
                    "status": "healthy",
                    "mode": "asyncpg",
                    "current_time": str(result["current_time"]),
                    "pg_version": result["pg_version"][:50],
                }
    except Exception as e:
        pass

    return {
        "status": "unhealthy",
        "error": "No database connection available",
        "supabase_url": SUPABASE_URL or "not configured",
    }
