"""
Chat Router
Nhận text từ Frontend, xử lý luồng Agent,
và stream kết quả về qua SSE.

Flow:
1. Frontend gửi câu hỏi -> /api/chat
2. FastAPI: Detect intent (predict vs dashboard vs query)
3. Nếu predict: Gọi predict tool
4. Nếu dashboard: Chạy multi-query → multi-chart
5. Nếu query: LLM sinh SQL -> Execute -> Chart -> Insight
6. Stream kết quả về Frontend qua SSE
"""

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

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

SQL_SYSTEM_PROMPT = """{guardrail}

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

# Predict keywords (both with and without Vietnamese diacritics)
PREDICT_KEYWORDS = [
    "dự đoán", "du doan", "forecast", "predict", "xu hướng tương lai",
    "dự báo", "du bao", "prediction", "tương lai", "tuong lai",
    "next month", "tháng tới", "thang toi", "quý tới", "quy toi",
    "năm tới", "nam toi", "sắp tới", "sap toi",
]

# Dashboard keywords
DASHBOARD_KEYWORDS = [
    "tạo dashboard", "tao dashboard", "dashboard tổng quan", "dashboard tong quan",
    "build dashboard", "create dashboard", "make dashboard",
    "dashboard theo dõi", "dashboard theo doi",
    "bảng điều khiển", "bang dieu khien",
    "tổng quan dashboard", "tong quan dashboard",
    "dashboard doanh thu", "dashboard don hang",
    "dashboard đơn hàng",
]

# Pre-defined dashboard queries for multi-chart generation
DASHBOARD_QUERIES = [
    {
        "name": "monthly_revenue",
        "title": "Doanh thu theo tháng",
        "sql": "SELECT * FROM v_monthly_revenue ORDER BY month",
        "chart_hint": "line chart showing revenue trend over months",
    },
    {
        "name": "daily_revenue",
        "title": "Doanh thu hàng ngày (30 ngày gần nhất)",
        "sql": "SELECT * FROM v_daily_revenue ORDER BY order_date DESC LIMIT 30",
        "chart_hint": "area chart showing daily revenue",
    },
    {
        "name": "top_products",
        "title": "Top 10 sản phẩm bán chạy",
        "sql": "SELECT * FROM v_product_performance ORDER BY total_revenue DESC LIMIT 10",
        "chart_hint": "horizontal bar chart showing top products by revenue",
    },
    {
        "name": "customer_segments",
        "title": "Doanh thu theo phân khúc khách hàng",
        "sql": "SELECT * FROM v_customer_segment_revenue",
        "chart_hint": "pie chart showing revenue by customer segment",
    },
]


class ChatRequest(BaseModel):
    """Request body cho chat."""
    message: str = Field(..., description="User message/question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    user_id: str = Field(default="default_user", description="User identifier")
    session_id: Optional[str] = Field(None, description="Chat session ID for history & context memory")


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


def _is_dashboard_request(message: str) -> bool:
    """Check if user message is asking for a dashboard."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in DASHBOARD_KEYWORDS)


def _build_fallback_chart(dq: dict, data: list) -> dict:
    """Build a fallback chart config when LLM-based chart generation fails."""
    if not data:
        return None

    keys = list(data[0].keys())
    numeric_keys = [k for k in keys if isinstance(data[0].get(k), (int, float))]
    text_keys = [k for k in keys if not isinstance(data[0].get(k), (int, float))]

    # Determine chart type from hint
    hint = dq.get("chart_hint", "").lower()
    if "pie" in hint:
        chart_type = "pie"
    elif "area" in hint:
        chart_type = "area"
    elif "line" in hint:
        chart_type = "line"
    else:
        chart_type = "bar"

    x_key = text_keys[0] if text_keys else keys[0]
    colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"]
    series = []
    for i, nk in enumerate(numeric_keys[:3]):
        series.append({
            "dataKey": nk,
            "name": nk.replace("_", " ").title(),
            "color": colors[i % len(colors)],
        })

    config = {
        "chart_type": chart_type,
        "title": dq["title"],
        "description": f"Phân tích theo {x_key}",
        "config": {
            "xAxis": {"dataKey": x_key, "label": x_key.replace("_", " ").title()},
            "yAxis": {"label": numeric_keys[0].replace("_", " ").title() if numeric_keys else ""},
            "series": series,
        },
        "data": data[:100],
        "dashboard_panel": dq["name"],
    }

    # For pie charts, add nameKey and dataKey at config level
    if chart_type == "pie" and text_keys and numeric_keys:
        config["config"]["nameKey"] = text_keys[0]
        config["config"]["dataKey"] = numeric_keys[0]

    return config


async def _process_dashboard(
    message: str,
    user_id: str
) -> AsyncGenerator[str, None]:
    """
    Xử lý yêu cầu tạo dashboard: Chạy nhiều queries và trả về multi-chart.
    Includes fallback chart generation when LLM fails.
    """
    yield await _stream_sse_event("status", {"message": "Đang tạo dashboard tổng quan..."})

    try:
        all_charts = []
        all_sqls = []
        failed_panels = []

        for i, dq in enumerate(DASHBOARD_QUERIES):
            yield await _stream_sse_event("status", {
                "message": f"Đang truy vấn: {dq['title']} ({i+1}/{len(DASHBOARD_QUERIES)})..."
            })

            # Execute query
            try:
                data = await execute_safe_query(dq["sql"])
            except Exception as e:
                logger.warning(f"Dashboard query failed for {dq['name']}: {e}")
                failed_panels.append({"name": dq["name"], "title": dq["title"], "error": str(e)})
                continue

            if not data:
                logger.info(f"Dashboard query returned empty for {dq['name']}")
                continue

            all_sqls.append({"name": dq["name"], "sql": dq["sql"]})

            # Generate chart config (with fallback)
            yield await _stream_sse_event("status", {
                "message": f"Đang tạo biểu đồ: {dq['title']}..."
            })

            try:
                chart_config = await generate_chart_config(data, dq["chart_hint"])
                chart_config["title"] = dq["title"]
                chart_config["dashboard_panel"] = dq["name"]
                chart_config["data"] = data[:100]
                all_charts.append(chart_config)
            except Exception as e:
                logger.warning(f"LLM chart generation failed for {dq['name']}: {e}, using fallback")
                # Fallback: build chart config without LLM
                fallback = _build_fallback_chart(dq, data)
                if fallback:
                    all_charts.append(fallback)

        # Emit all SQL queries used
        yield await _stream_sse_event("sql_generated", {
            "sql": "\n\n".join([f"-- {s['name']}\n{s['sql']}" for s in all_sqls]),
            "tool_used": "dashboard_builder",
            "queries": all_sqls,
        })

        # Emit data summary
        yield await _stream_sse_event("data_ready", {
            "row_count": sum(len(c.get("data", [])) for c in all_charts),
            "panel_count": len(all_charts),
            "preview": [{"panel": c.get("dashboard_panel"), "title": c.get("title")} for c in all_charts],
        })

        # Emit each chart as a separate event
        for chart in all_charts:
            yield await _stream_sse_event("chart", chart)

        # Generate overall insight
        yield await _stream_sse_event("status", {"message": "Đang phân tích insight tổng quan..."})
        try:
            summary_parts = []
            for chart in all_charts:
                chart_data = chart.get("data", [])
                if chart_data:
                    summary_parts.append(f"{chart.get('title', '')}: {len(chart_data)} records")

            insight = await generate_insight_summary(
                [{"dashboard_panels": len(all_charts), "summaries": summary_parts}],
                f"Tổng quan dashboard: {message}"
            )
        except Exception:
            insight = f"Dashboard tổng quan với {len(all_charts)} biểu đồ đã được tạo thành công."

        # Add failed panels info to insight if any
        if failed_panels:
            failed_info = ", ".join([p["title"] for p in failed_panels])
            insight += f"\n\nLưu ý: Một số panel không thể tải dữ liệu ({failed_info}). Vui lòng kiểm tra kết nối database."

        yield await _stream_sse_event("insight", {"text": insight})

        # Build completion message
        if all_charts:
            complete_msg = f"Dashboard hoàn thành! {len(all_charts)} biểu đồ đã được tạo."
        else:
            complete_msg = "Không thể tạo dashboard do không truy vấn được dữ liệu. Vui lòng kiểm tra kết nối database."

        yield await _stream_sse_event("complete", {
            "message": complete_msg,
            "tool_used": "dashboard_builder",
            "panel_count": len(all_charts),
        })

    except Exception as e:
        logger.error(f"Dashboard processing error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi tạo dashboard: {str(e)}"})


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
                    "content": SQL_SYSTEM_PROMPT.format(guardrail=READ_ONLY_GUARDRAIL)
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
    Hỗ trợ Chat History & Context Memory qua session_id.
    """
    logger.info(f"Chat request from {request.user_id}: {request.message[:100]}...")

    async def event_generator():
        from backend.services.chat_history_service import (
            create_session, save_message, get_context_messages, auto_generate_title
        )

        # ── Chat History: khởi tạo hoặc lấy session ────────────────────────────────
        session_id = request.session_id
        is_new_session = False
        if not session_id:
            # Tự động tạo session nếu frontend chưa gửi session_id
            try:
                session = await create_session(user_id=request.user_id)
                session_id = session.get("session_id", str(uuid.uuid4()))
                is_new_session = True
            except Exception:
                session_id = str(uuid.uuid4())

        message_id = str(uuid.uuid4())
        yield await _stream_sse_event("start", {
            "message_id": message_id,
            "user_message": request.message,
            "session_id": session_id,
        })

        # Lưu user message vào history
        try:
            await save_message(
                session_id=session_id,
                role="user",
                content=request.message,
                metadata={"message_id": message_id},
            )
            # Tự động đặt tiêu đề session từ message đầu tiên
            if is_new_session:
                asyncio.create_task(auto_generate_title(session_id, request.message))
        except Exception as e:
            logger.warning(f"Failed to save user message to history: {e}")

        # Lấy context từ lịch sử hội thoại (trừ message vừa gửi)
        context_messages = []
        try:
            context_messages = await get_context_messages(session_id)
            # Loại bỏ message vừa gửi (message cuối cùng) khỏi context
            if context_messages and context_messages[-1].get("content") == request.message:
                context_messages = context_messages[:-1]
        except Exception as e:
            logger.warning(f"Failed to get context messages: {e}")

        # ── Collect assistant response để lưu vào history ──────────────────────────
        assistant_response_parts = []

        # Route to predict, dashboard, or query based on intent
        if _is_predict_request(request.message):
            async for event in _process_predict(request.message, request.user_id):
                yield event
                # Thu thập insight từ predict response
                try:
                    parsed = json.loads(event.split("data: ", 1)[1]) if "data: " in event else {}
                    if "text" in parsed:
                        assistant_response_parts.append(parsed["text"])
                except Exception:
                    pass
        elif _is_dashboard_request(request.message):
            async for event in _process_dashboard(request.message, request.user_id):
                yield event
        else:
            async for event in _process_with_dify(
                message=request.message,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
            ):
                yield event
                # Thu thập text response từ Dify/Direct
                try:
                    if "data: " in event:
                        parsed = json.loads(event.split("data: ", 1)[1])
                        if "text" in parsed:
                            assistant_response_parts.append(parsed["text"])
                        elif "insight" in parsed:
                            assistant_response_parts.append(str(parsed["insight"]))
                except Exception:
                    pass

        # Lưu assistant response vào history
        if assistant_response_parts:
            assistant_content = " ".join(assistant_response_parts)
            try:
                await save_message(
                    session_id=session_id,
                    role="assistant",
                    content=assistant_content[:4000],  # Giới hạn 4000 ky tự
                    metadata={"message_id": message_id},
                )
            except Exception as e:
                logger.warning(f"Failed to save assistant message to history: {e}")

        yield await _stream_sse_event("done", {"status": "completed", "session_id": session_id})

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

        # Check if dashboard request
        if _is_dashboard_request(request.message):
            results = []
            for dq in DASHBOARD_QUERIES:
                try:
                    data = await execute_safe_query(dq["sql"])
                    chart = await generate_chart_config(data, dq["chart_hint"])
                    chart["title"] = dq["title"]
                    chart["data"] = data[:100]
                    results.append(chart)
                except Exception as e:
                    logger.warning(f"Dashboard query failed: {e}")

            return {
                "success": True,
                "tool_used": "dashboard_builder",
                "panel_count": len(results),
                "charts": results,
            }

        # Regular SQL query
        sql = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": SQL_SYSTEM_PROMPT.format(guardrail=READ_ONLY_GUARDRAIL)
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
