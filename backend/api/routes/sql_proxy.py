"""
SQL Proxy Router
Endpoint chạy SQL an toàn (chỉ SELECT) trên Supabase.
Được gọi bởi Dify Agent sau khi sinh SQL từ Text-to-SQL.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.db_executor import (
    execute_safe_query,
    health_check,
    prepare_safe_select_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sql", tags=["SQL Proxy"])


class SQLExecuteRequest(BaseModel):
    """Request body cho SQL execution."""
    sql: str = Field(..., description="SQL SELECT query to execute")
    params: Optional[List[Any]] = Field(None, description="Query parameters")
    timeout: int = Field(30, description="Query timeout in seconds", ge=1, le=120)


class SQLExecuteResponse(BaseModel):
    """Response body cho SQL execution."""
    success: bool
    data: List[Dict[str, Any]] = []
    row_count: int = 0
    executed_sql: Optional[str] = None
    error: Optional[str] = None


@router.post("/execute", response_model=SQLExecuteResponse)
async def execute_sql(request: SQLExecuteRequest):
    """
    Thực thi SQL query an toàn trên Supabase.
    Chỉ cho phép SELECT statements.

    Flow:
    - Dify Agent sinh SQL -> Gửi SQL về endpoint này
    - Validate SQL (chỉ SELECT)
    - Chạy trên Supabase qua asyncpg
    - Trả về mảng JSON data
    """
    logger.info(f"SQL Proxy request: {request.sql[:100]}...")

    try:
        safe_sql = prepare_safe_select_query(request.sql)
        data = await execute_safe_query(
            sql=safe_sql,
            params=request.params,
            timeout=request.timeout,
        )

        # Serialize special types (datetime, Decimal, etc.)
        serialized_data = json.loads(
            json.dumps(data, default=str, ensure_ascii=False)
        )

        return SQLExecuteResponse(
            success=True,
            data=serialized_data,
            row_count=len(serialized_data),
            executed_sql=safe_sql,
        )

    except ValueError as e:
        logger.warning(f"SQL validation error: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"SQL validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"SQL execution error: {str(e)}"
        )


@router.get("/health")
async def sql_health():
    """Kiểm tra kết nối database."""
    result = await health_check()
    if result["status"] == "unhealthy":
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/schemas")
async def list_schemas():
    """Liệt kê các schema có trong database."""
    try:
        data = await execute_safe_query("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name IN ('raw_staging', 'analytics_mart', 'system_metrics')
            ORDER BY schema_name
        """)
        return {"schemas": [row["schema_name"] for row in data]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{schema_name}")
async def list_tables(schema_name: str):
    """Liệt kê các bảng trong một schema."""
    if schema_name not in ("raw_staging", "analytics_mart", "system_metrics"):
        raise HTTPException(status_code=400, detail="Invalid schema name")

    try:
        data = await execute_safe_query(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name
            """,
            [schema_name]
        )
        return {"schema": schema_name, "tables": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/columns/{schema_name}/{table_name}")
async def list_columns(schema_name: str, table_name: str):
    """Liệt kê các cột trong một bảng."""
    if schema_name not in ("raw_staging", "analytics_mart", "system_metrics"):
        raise HTTPException(status_code=400, detail="Invalid schema name")

    try:
        data = await execute_safe_query(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
            """,
            [schema_name, table_name]
        )
        return {"schema": schema_name, "table": table_name, "columns": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
