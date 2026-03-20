"""
Chat Router
Nhận text từ Frontend, gọi Dify API, xử lý luồng Agent,
và stream kết quả về qua SSE.

Flow:
1. Frontend gửi câu hỏi -> /api/chat
2. FastAPI gửi text sang Dify API
3. Dify Agent: LLM quét Zilliz -> Sinh SQL -> Gọi /api/sql/execute
4. Nhận data JSON -> Manus Visualizer sinh cấu hình biểu đồ
5. Stream kết quả về Frontend qua SSE
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.db_executor import execute_safe_query
from backend.services.manus_visualizer import generate_chart_config, generate_insight_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Dify API configuration
DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_APP_TYPE = os.getenv("DIFY_APP_TYPE", "chat")  # chat or workflow


class ChatRequest(BaseModel):
    """Request body cho chat."""
    message: str = Field(..., description="User message/question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    user_id: str = Field(default="default_user", description="User identifier")


class ChatMessage(BaseModel):
    """Một message trong conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Optional[Dict[str, Any]] = None


async def _stream_sse_event(event: str, data: Any) -> str:
    """Format SSE event string."""
    serialized = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {serialized}\n\n"


async def _process_with_dify(
    message: str,
    conversation_id: Optional[str],
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Gửi message sang Dify API và stream response.
    Dify Agent sẽ tự động:
    1. Quét Zilliz để hiểu cấu trúc bảng
    2. Sinh SQL query
    3. Gọi lại /api/sql/execute
    4. Trả về kết quả
    """
    if not DIFY_API_KEY:
        # Fallback: Xử lý trực tiếp không qua Dify
        yield await _stream_sse_event("status", {"message": "Processing without Dify (API key not configured)..."})
        async for event in _process_direct(message, user_id):
            yield event
        return

    try:
        yield await _stream_sse_event("status", {"message": "Đang gửi câu hỏi tới AI Agent..."})

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{DIFY_API_URL}/chat-messages",
                json={
                    "inputs": {},
                    "query": message,
                    "response_mode": "streaming",
                    "conversation_id": conversation_id or "",
                    "user": user_id,
                },
                headers={
                    "Authorization": f"Bearer {DIFY_API_KEY}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code != 200:
                yield await _stream_sse_event("error", {
                    "message": f"Dify API error: {response.status_code}"
                })
                return

            # Stream Dify response
            full_answer = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("event", "")

                        if event_type == "message":
                            chunk = data.get("answer", "")
                            full_answer += chunk
                            yield await _stream_sse_event("message_chunk", {
                                "chunk": chunk,
                                "conversation_id": data.get("conversation_id", ""),
                            })

                        elif event_type == "message_end":
                            yield await _stream_sse_event("message_complete", {
                                "full_answer": full_answer,
                                "conversation_id": data.get("conversation_id", ""),
                                "metadata": data.get("metadata", {}),
                            })

                        elif event_type == "agent_thought":
                            yield await _stream_sse_event("agent_thought", {
                                "thought": data.get("thought", ""),
                                "tool": data.get("tool", ""),
                                "tool_input": data.get("tool_input", ""),
                            })

                    except json.JSONDecodeError:
                        continue

    except httpx.TimeoutException:
        yield await _stream_sse_event("error", {"message": "Dify API timeout"})
    except Exception as e:
        logger.error(f"Dify API error: {e}")
        yield await _stream_sse_event("error", {"message": str(e)})


async def _process_direct(
    message: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Xử lý trực tiếp không qua Dify.
    Sử dụng OpenAI để sinh SQL, thực thi, và sinh biểu đồ.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    yield await _stream_sse_event("status", {"message": "Đang phân tích câu hỏi..."})

    try:
        # Step 1: Sinh SQL từ câu hỏi
        sql_response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a SQL expert for a sales analytics database on PostgreSQL (Supabase).
Available schemas and tables:
- analytics_mart.fact_sales (sale_id, order_date, product_id, customer_id, quantity, unit_price, total_amount, discount, channel, payment_method)
- analytics_mart.dim_products (product_id, product_name, category, sub_category, brand, unit_price)
- analytics_mart.dim_customers (customer_id, customer_name, email, segment, region, city, country)
- analytics_mart.v_daily_revenue (order_date, total_orders, total_quantity, total_revenue, avg_order_value)
- analytics_mart.v_monthly_revenue (month, total_orders, total_revenue, avg_order_value)
- analytics_mart.v_product_performance (product_id, product_name, category, total_orders, total_quantity, total_revenue)
- analytics_mart.v_customer_segment_revenue (segment, region, total_customers, total_orders, total_revenue)

Generate ONLY a SELECT SQL query. Return ONLY the SQL, no explanation.
If the question is not about data, return: SELECT 'I can only answer data-related questions' as message"""
                },
                {"role": "user", "content": message}
            ],
            temperature=0.1,
            max_tokens=500,
        )

        sql_query = sql_response.choices[0].message.content.strip()
        # Clean SQL (remove markdown code blocks if any)
        if sql_query.startswith("```"):
            sql_query = sql_query.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        yield await _stream_sse_event("sql_generated", {"sql": sql_query})
        yield await _stream_sse_event("status", {"message": "Đang truy vấn dữ liệu..."})

        # Step 2: Thực thi SQL
        data = await execute_safe_query(sql_query)

        yield await _stream_sse_event("data_ready", {
            "row_count": len(data),
            "preview": data[:5] if data else [],
        })

        # Step 3: Sinh cấu hình biểu đồ
        yield await _stream_sse_event("status", {"message": "Đang tạo biểu đồ..."})
        chart_config = await generate_chart_config(data, message)

        yield await _stream_sse_event("chart", chart_config)

        # Step 4: Sinh insight summary
        yield await _stream_sse_event("status", {"message": "Đang phân tích insight..."})
        insight = await generate_insight_summary(data, message)

        yield await _stream_sse_event("insight", {"text": insight})

        # Step 5: Hoàn thành
        yield await _stream_sse_event("complete", {
            "message": "Hoàn thành phân tích!",
            "sql": sql_query,
            "row_count": len(data),
        })

    except ValueError as e:
        yield await _stream_sse_event("error", {"message": f"SQL Error: {str(e)}"})
    except Exception as e:
        logger.error(f"Direct processing error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Error: {str(e)}"})


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Chat endpoint với SSE streaming.
    Frontend gọi endpoint này và nhận stream events.
    """
    logger.info(f"Chat request from {request.user_id}: {request.message[:100]}...")

    async def event_generator():
        yield await _stream_sse_event("start", {
            "message_id": str(uuid.uuid4()),
            "user_message": request.message,
        })

        async for event in _process_with_dify(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
        ):
            yield event

        yield await _stream_sse_event("done", {"status": "completed"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query")
async def chat_query(request: ChatRequest):
    """
    Chat endpoint không streaming (cho testing).
    Trả về kết quả đầy đủ trong một response.
    """
    logger.info(f"Query request from {request.user_id}: {request.message[:100]}...")

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

        # Sinh SQL
        sql_response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a SQL expert. Generate SELECT SQL for PostgreSQL.
Available tables: analytics_mart.fact_sales, analytics_mart.dim_products, analytics_mart.dim_customers,
analytics_mart.v_daily_revenue, analytics_mart.v_monthly_revenue, analytics_mart.v_product_performance.
Return ONLY SQL."""
                },
                {"role": "user", "content": request.message}
            ],
            temperature=0.1,
        )

        sql = sql_response.choices[0].message.content.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # Thực thi SQL
        data = await execute_safe_query(sql)

        # Sinh biểu đồ
        chart = await generate_chart_config(data, request.message)

        # Sinh insight
        insight = await generate_insight_summary(data, request.message)

        return {
            "success": True,
            "sql": sql,
            "data": data[:100],
            "row_count": len(data),
            "chart": chart,
            "insight": insight,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
