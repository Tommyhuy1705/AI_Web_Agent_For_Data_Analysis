"""
Chat Router
Nhận text từ Frontend, xử lý luồng Agent,
và stream kết quả về qua SSE.

Flow:
1. Frontend gửi câu hỏi -> /api/chat
2. FastAPI: Detect intent (predict vs query)
3. Nếu predict: Gọi predict tool
4. Nếu query: LLM sinh SQL -> Execute -> Chart -> Insight
5. Stream kết quả về Frontend qua SSE
"""

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.db_executor import execute_safe_query
from backend.services.manus_visualizer import generate_chart_config, generate_insight_summary
from backend.services.llm_client import chat_completion, is_configured, get_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Dify API configuration
DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_APP_TYPE = os.getenv("DIFY_APP_TYPE", "chat")

SCHEMA_FALLBACK_SUMMARY = """Read-only analytics schema (fallback when vector context is unavailable):
- analytics_mart.fact_sales(order_date, product_id, customer_id, quantity, unit_price, total_amount, discount, channel, payment_method)
- analytics_mart.dim_products(product_id, product_name, category, sub_category, brand, unit_price)
- analytics_mart.dim_customers(customer_id, customer_name, email, segment, region, city, country)
- analytics_mart.v_daily_revenue(order_date, total_orders, total_quantity, total_revenue, avg_order_value)
- analytics_mart.v_monthly_revenue(month, total_orders, total_revenue, avg_order_value)
"""

READ_ONLY_GUARDRAIL = """You are a read-only data analytics assistant.
Never generate or suggest SQL that writes/modifies/deletes schema or data.
Refuse any request involving INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT, REVOKE.
If user asks destructive/admin action, return only:
SELECT 'Read-only policy: destructive or mutating actions are not allowed' AS message
"""

# Predict keywords (both with and without Vietnamese diacritics)
PREDICT_KEYWORDS = [
    "dự đoán", "du doan", "forecast", "predict", "xu hướng tương lai",
    "dự báo", "du bao", "prediction", "tương lai", "tuong lai",
    "next month", "tháng tới", "thang toi", "quý tới", "quy toi",
    "năm tới", "nam toi", "sắp tới", "sap toi",
]


class ChatRequest(BaseModel):
    """Request body cho chat."""
    message: str = Field(..., description="User message/question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    user_id: str = Field(default="default_user", description="User identifier")


class ChatMessage(BaseModel):
    """Một message trong conversation."""
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


async def _stream_sse_event(event: str, data: Any) -> str:
    """Format SSE event string."""
    serialized = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {serialized}\n\n"


def _friendly_ai_overload_message() -> str:
    return "He thong AI dang qua tai, vui long thu lai sau vai giay."


def _is_predict_request(message: str) -> bool:
    """Check if user message is asking for prediction/forecast."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in PREDICT_KEYWORDS)


async def _process_predict(
    message: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Xử lý yêu cầu dự đoán: Gọi predict tool thay vì SQL query.
    """
    from backend.ml_models.time_series import predict_revenue, generate_strategic_insight

    yield await _stream_sse_event("status", {"message": "Đang phân tích xu hướng và dự đoán..."})

    try:
        # Step 1: Get historical data for prediction
        yield await _stream_sse_event("sql_generated", {
            "sql": "SELECT month, total_revenue FROM v_monthly_revenue ORDER BY month",
            "tool_used": "predict_revenue"
        })

        # Step 2: Run prediction
        yield await _stream_sse_event("status", {"message": "Đang chạy mô hình dự đoán..."})
        predictions = await predict_revenue(periods=3)

        # Step 3: Get historical data for chart
        historical_data = await execute_safe_query(
            "SELECT month, total_revenue FROM v_monthly_revenue ORDER BY month"
        )

        # Step 4: Build combined chart data
        chart_data = []
        for row in historical_data:
            chart_data.append({
                "month": str(row.get("month", "")),
                "actual": row.get("total_revenue", 0),
                "predicted": None,
            })

        for pred in predictions.get("predictions", []):
            chart_data.append({
                "month": pred["month"],
                "actual": None,
                "predicted": pred["predicted_revenue"],
            })

        yield await _stream_sse_event("data_ready", {
            "row_count": len(chart_data),
            "preview": chart_data[:5],
            "predictions": predictions,
        })

        # Step 5: Chart config
        yield await _stream_sse_event("status", {"message": "Đang tạo biểu đồ dự đoán..."})
        chart_config = {
            "chart_type": "composed",
            "title": "Dự đoán doanh thu",
            "description": f"Doanh thu thực tế và dự đoán {len(predictions.get('predictions', []))} tháng tới",
            "config": {
                "xAxis": {"dataKey": "month", "label": "Tháng"},
                "yAxis": {"label": "Doanh thu (VND)"},
                "series": [
                    {"dataKey": "actual", "name": "Thực tế", "color": "#3B82F6", "type": "bar"},
                    {"dataKey": "predicted", "name": "Dự đoán", "color": "#F59E0B", "type": "line"},
                ],
            },
            "data": chart_data,
        }
        yield await _stream_sse_event("chart", chart_config)

        # Step 6: AI Insight
        yield await _stream_sse_event("status", {"message": "Đang phân tích insight chiến lược..."})
        try:
            insight = await generate_strategic_insight(predictions)
        except Exception:
            insight = f"Dự đoán doanh thu {len(predictions.get('predictions', []))} tháng tới. Xu hướng: {predictions.get('trend', 'N/A')}."

        yield await _stream_sse_event("insight", {"text": insight})

        yield await _stream_sse_event("complete", {
            "message": "Hoàn thành dự đoán!",
            "tool_used": "predict_revenue",
            "predictions": predictions.get("predictions", []),
        })

    except Exception as e:
        logger.error(f"Predict processing error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi dự đoán: {str(e)}"})


async def _process_with_dify(
    message: str,
    conversation_id: Optional[str],
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Gửi message sang Dify API và stream response.
    Fallback sang _process_direct nếu Dify không khả dụng.
    """
    if not DIFY_API_KEY:
        yield await _stream_sse_event("status", {"message": "Processing without Dify..."})
        async for event in _process_direct(message, user_id):
            yield event
        return

    try:
        yield await _stream_sse_event("status", {"message": "Đang gửi câu hỏi tới AI Agent..."})

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{DIFY_API_URL}/chat-messages",
                json={
                    "inputs": {
                        "schema_fallback": SCHEMA_FALLBACK_SUMMARY,
                        "read_only_policy": READ_ONLY_GUARDRAIL,
                    },
                    "query": f"{READ_ONLY_GUARDRAIL}\n\nUser question: {message}",
                    "response_mode": "streaming",
                    "conversation_id": conversation_id or "",
                    "user": user_id,
                },
                headers={
                    "Authorization": f"Bearer {DIFY_API_KEY}",
                    "Content-Type": "application/json",
                },
            ) as response:
                if response.status_code != 200:
                    error_body = ""
                    async for chunk in response.aiter_bytes():
                        error_body += chunk.decode("utf-8", errors="ignore")
                    logger.warning(f"Dify API error {response.status_code}: {error_body[:200]}")

                    if response.status_code in (429, 502, 503, 504):
                        yield await _stream_sse_event("error", {"message": _friendly_ai_overload_message()})
                    else:
                        # Fallback to direct processing when Dify fails
                        yield await _stream_sse_event("status", {"message": "Dify không khả dụng, chuyển sang xử lý trực tiếp..."})
                        async for event in _process_direct(message, user_id):
                            yield event
                    return

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
        yield await _stream_sse_event("error", {"message": _friendly_ai_overload_message()})
    except Exception as e:
        logger.error(f"Dify API error: {e}")
        # Fallback to direct processing
        yield await _stream_sse_event("status", {"message": "Chuyển sang xử lý trực tiếp..."})
        async for event in _process_direct(message, user_id):
            yield event


async def _process_direct(
    message: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Xử lý trực tiếp không qua Dify.
    Sử dụng LLM (Qwen/OpenAI) để sinh SQL, thực thi, và sinh biểu đồ.
    """
    if not is_configured():
        yield await _stream_sse_event("error", {
            "message": "Chưa cấu hình LLM. Vui lòng set DASHSCOPE_API_KEY hoặc OPENAI_API_KEY."
        })
        return

    yield await _stream_sse_event("status", {
        "message": f"Đang phân tích câu hỏi (via {get_provider()})..."
    })

    try:
        # Step 1: Sinh SQL từ câu hỏi
        sql_query = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": f"""{READ_ONLY_GUARDRAIL}

You are a SQL expert for a sales analytics database on PostgreSQL (Supabase PostgREST).

CRITICAL RULES:
1. NEVER use schema prefix (no "analytics_mart."). Use plain table/view names.
2. NEVER use column aliases (no AS). PostgREST does not support them.
3. NEVER use aggregate functions (SUM, COUNT, AVG, GROUP BY). Use pre-computed views.
4. ALWAYS prefer views over raw tables. Views already have aggregated data.
5. Return ONLY raw SQL. No markdown code blocks, no explanation.

Tables:
- fact_sales: sale_id(int), order_date(date), product_id(int), customer_id(int), quantity(int), unit_price(numeric), total_amount(numeric), discount(numeric), channel(text), payment_method(text)
- dim_products: product_id(int), product_name(text), category(text), sub_category(text), brand(text), unit_price(numeric)
- dim_customers: customer_id(int), customer_name(text), email(text), segment(text: 'Premium'|'Standard'|'Basic'), region(text), city(text), country(text)

Views (pre-aggregated, use these first):
- v_daily_revenue: order_date(date), total_orders(int), total_quantity(int), total_revenue(numeric), avg_order_value(numeric)
- v_monthly_revenue: month(text, format 'YYYY-MM' e.g. '2025-03'), total_orders(int), total_revenue(numeric), avg_order_value(numeric)
- v_product_performance: product_id(int), product_name(text), category(text), total_orders(int), total_quantity(int), total_revenue(numeric)
- v_customer_segment_revenue: segment(text), region(text), total_customers(int), total_orders(int), total_revenue(numeric)

Examples:
- "Doanh thu tháng 3": SELECT * FROM v_monthly_revenue WHERE month = '2025-03'
- "Top 5 sản phẩm": SELECT * FROM v_product_performance ORDER BY total_revenue DESC LIMIT 5
- "Doanh thu theo khu vực": SELECT * FROM v_customer_segment_revenue

If the question is not about data, return: SELECT 'I can only answer data-related questions'"""
                },
                {"role": "user", "content": message}
            ],
            temperature=0.1,
            max_tokens=500,
        )

        sql_query = sql_query.strip()
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
    except httpx.TimeoutException:
        yield await _stream_sse_event("error", {"message": _friendly_ai_overload_message()})
    except Exception as e:
        logger.error(f"Direct processing error: {e}", exc_info=True)
        error_text = str(e).lower()
        if "timeout" in error_text or "rate" in error_text or "429" in error_text:
            yield await _stream_sse_event("error", {"message": _friendly_ai_overload_message()})
        else:
            yield await _stream_sse_event("error", {"message": f"Lỗi: {str(e)}"})


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

        # Route to predict or query based on intent
        if _is_predict_request(request.message):
            async for event in _process_predict(request.message, request.user_id):
                yield event
        else:
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
        if not is_configured():
            raise HTTPException(status_code=500, detail="No LLM provider configured")

        # Check if predict request
        if _is_predict_request(request.message):
            from backend.ml_models.time_series import predict_revenue, generate_strategic_insight
            predictions = await predict_revenue(periods=3)
            try:
                insight = await generate_strategic_insight(predictions)
            except Exception:
                insight = f"Dự đoán {len(predictions.get('predictions', []))} tháng tới."

            return {
                "success": True,
                "tool_used": "predict_revenue",
                "predictions": predictions,
                "insight": insight,
            }

        # Regular SQL query
        sql = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": f"""{READ_ONLY_GUARDRAIL}

You are a SQL expert for PostgreSQL (Supabase PostgREST).
NEVER use schema prefix. NEVER use AS aliases. NEVER use aggregate functions.
Use pre-computed views: v_daily_revenue, v_monthly_revenue, v_product_performance, v_customer_segment_revenue.
Tables: fact_sales, dim_products, dim_customers.
v_monthly_revenue.month is text format 'YYYY-MM'. v_product_performance has: total_orders, total_quantity, total_revenue.
Return ONLY raw SQL."""
                },
                {"role": "user", "content": request.message}
            ],
            temperature=0.1,
        )

        sql = sql.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data = await execute_safe_query(sql)
        chart = await generate_chart_config(data, request.message)
        insight = await generate_insight_summary(data, request.message)

        return {
            "success": True,
            "sql": sql,
            "data": data[:100],
            "row_count": len(data),
            "chart": chart,
            "insight": insight,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
