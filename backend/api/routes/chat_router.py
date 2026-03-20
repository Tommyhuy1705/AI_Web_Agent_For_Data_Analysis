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

Predict Tool Integration:
- Khi user hỏi về "dự đoán", "forecast", "predict", agent sẽ tự động
  gọi predict_revenue endpoint thay vì chỉ query SQL.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.db_executor import execute_safe_query
from backend.services.manus_visualizer import generate_chart_config, generate_insight_summary
from backend.ml_models.time_series import predict_revenue, generate_strategic_insight

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Dify API configuration
DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_APP_TYPE = os.getenv("DIFY_APP_TYPE", "chat")  # chat or workflow

# Predict keywords detection
PREDICT_KEYWORDS = [
    "dự đoán", "dự báo", "forecast", "predict", "prediction",
    "xu hướng tương lai", "tháng tới", "quý tới", "năm tới",
    "doanh thu sắp tới", "doanh thu tương lai", "revenue forecast",
    "trend", "next month", "next quarter",
]


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


def _is_predict_query(message: str) -> bool:
    """Kiểm tra xem câu hỏi có liên quan đến dự đoán không."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in PREDICT_KEYWORDS)


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
    # Dify API key starting with 'dataset-' is for Knowledge API, not App API
    # We need an 'app-' key for chat. Fallback to direct processing.
    if not DIFY_API_KEY or DIFY_API_KEY.startswith("dataset-"):
        yield await _stream_sse_event("status", {"message": "Processing with AI Agent (OpenAI direct)..."})
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


async def _process_predict(
    message: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Xử lý câu hỏi dự đoán doanh thu.
    Flow:
    1. Query dữ liệu lịch sử từ v_monthly_revenue
    2. Gọi predict_revenue() để train model và dự đoán
    3. Sinh biểu đồ kết hợp (historical + predicted)
    4. Sinh insight chiến lược
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    yield await _stream_sse_event("status", {"message": "Đang phân tích yêu cầu dự đoán..."})

    try:
        # Step 1: Parse predict parameters from user message
        periods = 3  # default
        period_type = "month"

        # Detect number of periods
        num_match = re.search(r'(\d+)\s*(tháng|quý|month|quarter)', message.lower())
        if num_match:
            periods = min(int(num_match.group(1)), 12)
            if num_match.group(2) in ("quý", "quarter"):
                period_type = "quarter"

        yield await _stream_sse_event("status", {
            "message": f"Đang lấy dữ liệu lịch sử để dự đoán {periods} {period_type}..."
        })

        # Step 2: Query historical data (no aliases - PostgREST doesn't support them)
        historical_query = """
            SELECT month, total_revenue
            FROM v_monthly_revenue
            ORDER BY month ASC
        """
        yield await _stream_sse_event("sql_generated", {"sql": historical_query})

        historical_data = await execute_safe_query(historical_query)

        if len(historical_data) < 3:
            yield await _stream_sse_event("error", {
                "message": f"Cần ít nhất 3 kỳ dữ liệu lịch sử. Hiện có: {len(historical_data)}"
            })
            return

        formatted_data = [
            {"date": str(row["month"]), "revenue": float(row["total_revenue"])}
            for row in historical_data
        ]

        yield await _stream_sse_event("data_ready", {
            "row_count": len(formatted_data),
            "preview": formatted_data[:5],
        })

        # Step 3: Run prediction
        yield await _stream_sse_event("status", {"message": "Đang chạy mô hình dự đoán (Polynomial Regression)..."})

        result = await predict_revenue(
            historical_data=formatted_data,
            periods=periods,
            period_type=period_type,
        )

        if result.get("error"):
            yield await _stream_sse_event("error", {"message": result["error"]})
            return

        # Step 4: Build combined chart (historical + predicted)
        yield await _stream_sse_event("status", {"message": "Đang tạo biểu đồ dự đoán..."})

        chart_data = []
        for row in formatted_data:
            chart_data.append({
                "period": row["date"][:7] if len(row["date"]) > 7 else row["date"],
                "actual": row["revenue"],
                "predicted": None,
            })

        for pred in result.get("predictions", []):
            chart_data.append({
                "period": pred["period"],
                "actual": None,
                "predicted": pred["predicted_value"],
            })

        chart_config = {
            "chart_type": "composed",
            "title": f"Dự đoán doanh thu {periods} {period_type} tới",
            "description": f"Mô hình: Polynomial Regression (R²={result.get('metrics', {}).get('r2_score', 0):.4f})",
            "config": {
                "xAxis": {"dataKey": "period", "label": "Kỳ"},
                "series": [
                    {"dataKey": "actual", "name": "Doanh thu thực tế", "color": "#3B82F6", "type": "bar"},
                    {"dataKey": "predicted", "name": "Dự đoán", "color": "#F59E0B", "type": "line"},
                ],
            },
            "data": chart_data,
            "predictions": result.get("predictions", []),
            "metrics": result.get("metrics", {}),
            "trend": result.get("trend", {}),
        }

        yield await _stream_sse_event("chart", chart_config)

        # Step 5: Generate strategic insight
        yield await _stream_sse_event("status", {"message": "Đang sinh báo cáo insight chiến lược..."})

        insight = await generate_strategic_insight(result)

        yield await _stream_sse_event("insight", {"text": insight})

        # Step 6: Complete
        yield await _stream_sse_event("complete", {
            "message": "Hoàn thành dự đoán!",
            "tool_used": "predict_revenue",
            "periods": periods,
            "period_type": period_type,
            "row_count": len(formatted_data),
        })

    except Exception as e:
        logger.error(f"Predict processing error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Prediction Error: {str(e)}"})


async def _process_direct(
    message: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Xử lý trực tiếp không qua Dify.
    Sử dụng OpenAI để sinh SQL, thực thi, và sinh biểu đồ.
    Tự động detect predict queries và route sang predict tool.
    """
    # Check if this is a predict query
    if _is_predict_query(message):
        async for event in _process_predict(message, user_id):
            yield event
        return

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
Available tables in public schema:
- fact_sales (sale_id, order_date, product_id, customer_id, quantity, unit_price, total_amount, discount, channel, payment_method)
- dim_products (product_id, product_name, category, sub_category, brand, unit_price)
- dim_customers (customer_id, customer_name, email, segment, region, city, country)
- v_daily_revenue (order_date, total_orders, total_quantity, total_revenue, avg_order_value)
- v_monthly_revenue (month, total_orders, total_revenue, avg_order_value)
- v_product_performance (product_id, product_name, category, total_orders, total_quantity, total_revenue)
- v_customer_segment_revenue (segment, region, total_customers, total_orders, total_revenue)

IMPORTANT RULES:
1. Do NOT use schema prefix (no analytics_mart. or public.). Just use table names directly.
2. Generate ONLY a SELECT SQL query.
3. Return ONLY the SQL, no explanation, no markdown code blocks.
4. Use proper PostgreSQL syntax.
5. If the question is not about data, return: SELECT 'I can only answer data-related questions' as message"""
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
        # Check if this is a predict query
        if _is_predict_query(request.message):
            return await _handle_predict_query(request)

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

        # Sinh SQL
        sql_response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a SQL expert. Generate SELECT SQL for PostgreSQL.
Available tables (public schema, NO schema prefix):
- fact_sales, dim_products, dim_customers, v_daily_revenue, v_monthly_revenue, v_product_performance, v_customer_segment_revenue.
Return ONLY SQL, no markdown."""
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


async def _handle_predict_query(request: ChatRequest) -> dict:
    """Handle predict query in non-streaming mode."""
    import re as _re

    periods = 3
    period_type = "month"

    num_match = _re.search(r'(\d+)\s*(tháng|quý|month|quarter)', request.message.lower())
    if num_match:
        periods = min(int(num_match.group(1)), 12)
        if num_match.group(2) in ("quý", "quarter"):
            period_type = "quarter"

    # Query historical data (no aliases - PostgREST doesn't support them)
    historical_data = await execute_safe_query("""
        SELECT month, total_revenue
        FROM v_monthly_revenue
        ORDER BY month ASC
    """)

    formatted_data = [
        {"date": str(row["month"]), "revenue": float(row["total_revenue"])}
        for row in historical_data
    ]

    # Run prediction
    result = await predict_revenue(
        historical_data=formatted_data,
        periods=periods,
        period_type=period_type,
    )

    # Build chart data
    chart_data = []
    for row in formatted_data:
        chart_data.append({
            "period": row["date"][:7] if len(row["date"]) > 7 else row["date"],
            "actual": row["revenue"],
            "predicted": None,
        })
    for pred in result.get("predictions", []):
        chart_data.append({
            "period": pred["period"],
            "actual": None,
            "predicted": pred["predicted_value"],
        })

    chart_config = {
        "chart_type": "composed",
        "title": f"Dự đoán doanh thu {periods} {period_type} tới",
        "config": {
            "xAxis": {"dataKey": "period", "label": "Kỳ"},
            "series": [
                {"dataKey": "actual", "name": "Doanh thu thực tế", "color": "#3B82F6", "type": "bar"},
                {"dataKey": "predicted", "name": "Dự đoán", "color": "#F59E0B", "type": "line"},
            ],
        },
        "data": chart_data,
    }

    # Generate insight
    insight = await generate_strategic_insight(result)

    return {
        "success": True,
        "tool_used": "predict_revenue",
        "sql": "SELECT month as date, total_revenue as revenue FROM v_monthly_revenue ORDER BY month ASC",
        "data": chart_data,
        "row_count": len(chart_data),
        "chart": chart_config,
        "insight": insight,
        "predictions": result.get("predictions", []),
        "metrics": result.get("metrics", {}),
        "trend": result.get("trend", {}),
    }
