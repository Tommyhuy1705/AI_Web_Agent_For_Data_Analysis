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

# ============================================================
# Tool Descriptions for Intent Routing
# ============================================================
#
# Tool market_quant_scraper (Gọi TinyFish):
#   Chỉ kích hoạt khi người dùng hỏi về con số cụ thể của đối thủ:
#   Giá bán, số lượng, phần trăm giảm giá trên Shopee/Lazada.
#
# Tool market_qual_search (Gọi Exa):
#   Chỉ kích hoạt khi người dùng hỏi TẠI SAO (Why) có biến động,
#   cần tìm tin tức, bối cảnh thời tiết, xu hướng thị trường, lý do vĩ mô.
#
# Logic gộp (Hybrid):
#   Nếu phát hiện doanh thu rớt, LLM tự động gọi cả TinyFish (xem đối thủ
#   có phá giá không) và Exa (xem có trend gì xấu không) để đúc kết thành
#   1 insight hoàn chỉnh.
# ============================================================

# Predict keywords (both with and without Vietnamese diacritics)
PREDICT_KEYWORDS = [
    "dự đoán", "du doan", "forecast", "predict", "xu hướng tương lai",
    "dự báo", "du bao", "prediction", "tương lai", "tuong lai",
    "next month", "tháng tới", "thang toi", "quý tới", "quy toi",
    "năm tới", "nam toi", "sắp tới", "sap toi",
]

# Market Quantitative keywords (TinyFish - giá đối thủ, số lượng)
MARKET_QUANT_KEYWORDS = [
    # Giá đối thủ
    "giá đối thủ", "gia doi thu", "competitor price", "đối thủ bán giá",
    "giá shopee", "gia shopee", "giá lazada", "gia lazada", "giá tiki", "gia tiki",
    "so sánh giá", "so sanh gia", "price comparison",
    # Số lượng bán
    "số lượng bán", "so luong ban", "items sold", "đã bán", "da ban",
    # Giảm giá
    "giảm giá đối thủ", "giam gia doi thu", "discount competitor",
    "phần trăm giảm", "phan tram giam", "% giảm",
    # Crawl / scrape
    "cào dữ liệu", "cao du lieu", "crawl", "scrape", "market intel",
    "tình báo thị trường", "tinh bao thi truong",
]

# Market Qualitative keywords (Exa - tin tức, bối cảnh, lý do)
MARKET_QUAL_KEYWORDS = [
    # Tại sao / Why
    "tại sao", "tai sao", "why", "lý do", "ly do", "nguyên nhân", "nguyen nhan",
    "vì sao", "vi sao", "reason", "cause",
    # Tin tức
    "tin tức", "tin tuc", "news", "bài báo", "bai bao", "article",
    # Xu hướng
    "xu hướng", "xu huong", "trend", "market trend", "xu thế", "xu the",
    # Bối cảnh
    "bối cảnh", "boi canh", "context", "background",
    # Thời tiết / vĩ mô
    "thời tiết", "thoi tiet", "weather", "vĩ mô", "vi mo", "macro",
    # Sự kiện
    "sự kiện", "su kien", "event", "tin mới nhất", "tin moi nhat",
]

# Hybrid trigger keywords (doanh thu rớt → gọi cả TinyFish + Exa)
HYBRID_REVENUE_DROP_KEYWORDS = [
    "doanh thu giảm", "doanh thu rot", "doanh thu rớt", "revenue drop",
    "revenue decline", "doanh thu xuống", "doanh thu xuong",
    "doanh số giảm", "doanh so giam", "sales drop", "sales decline",
    "tại sao doanh thu", "tai sao doanh thu", "why revenue",
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


def _is_market_quant_request(message: str) -> bool:
    """
    Tool: market_quant_scraper (TinyFish)
    Chỉ kích hoạt khi người dùng hỏi về con số cụ thể của đối thủ:
    Giá bán, số lượng, phần trăm giảm giá trên Shopee/Lazada.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in MARKET_QUANT_KEYWORDS)


def _is_market_qual_request(message: str) -> bool:
    """
    Tool: market_qual_search (Exa)
    Chỉ kích hoạt khi người dùng hỏi TẠI SAO (Why) có biến động,
    cần tìm tin tức, bối cảnh thời tiết, xu hướng thị trường, lý do vĩ mô.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in MARKET_QUAL_KEYWORDS)


def _is_hybrid_revenue_drop(message: str) -> bool:
    """
    Logic gộp (Hybrid): Phát hiện câu hỏi về doanh thu rớt.
    Tự động gọi cả TinyFish + Exa để đúc kết insight hoàn chỉnh.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in HYBRID_REVENUE_DROP_KEYWORDS)


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


async def _process_market_quant(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Tool: market_quant_scraper (TinyFish)
    Xử lý yêu cầu định lượng: cào giá đối thủ từ Shopee/Tiki.
    """
    from backend.services.tinyfish_service import (
        is_configured as tf_configured,
        run_competitor_crawl,
        get_market_intel_summary,
    )

    yield await _stream_sse_event("status", {
        "message": "🔍 Đang cào dữ liệu đối thủ từ Shopee/Tiki (TinyFish)...",
        "tool": "market_quant_scraper",
    })

    if not tf_configured():
        yield await _stream_sse_event("insight", {
            "text": "TinyFish chưa được cấu hình. Vui lòng thêm TINYFISH_API_KEY vào .env."
        })
        yield await _stream_sse_event("complete", {"message": "TinyFish not configured", "tool_used": "market_quant_scraper"})
        return

    try:
        # Chạy crawl đối thủ
        yield await _stream_sse_event("status", {"message": "⏳ Đang cào dữ liệu... (có thể mất 30-60 giây)"})
        await run_competitor_crawl()

        # Lấy tóm tắt dữ liệu vừa cào
        summary = await get_market_intel_summary()

        if summary:
            yield await _stream_sse_event("data_ready", {
                "row_count": summary.get("total_records", 0),
                "preview": summary.get("recent_crawls", [])[:5],
            })
            insight_text = (
                f"📊 **Kết quả Tình báo Thị trường (TinyFish)**\n"
                f"- Tổng bản ghi: {summary.get('total_records', 0)}\n"
                f"- Nguồn: {', '.join(summary.get('sources', []))}\n"
                f"- Cập nhật lúc: {summary.get('last_crawled_at', 'N/A')}\n\n"
                f"Dữ liệu đã được lưu vào bảng raw_market_intel. "
                f"Hãy hỏi tôi về giá cụ thể của từng sản phẩm!"
            )
        else:
            insight_text = "Dữ liệu đối thủ đã được cào. Kiểm tra bảng raw_market_intel trong Supabase."

        yield await _stream_sse_event("insight", {"text": insight_text})
        yield await _stream_sse_event("complete", {
            "message": "Cào dữ liệu đối thủ hoàn thành!",
            "tool_used": "market_quant_scraper",
        })

    except Exception as e:
        logger.error(f"Market quant scraper error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi cào dữ liệu: {str(e)}"})


async def _process_market_qual(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Tool: market_qual_search (Exa)
    Xử lý yêu cầu định tính: tìm tin tức, bối cảnh, lý do biến động.
    """
    from backend.services.exa_service import (
        is_configured as exa_configured,
        search_market_news,
        get_market_context,
    )

    yield await _stream_sse_event("status", {
        "message": "📰 Đang tìm kiếm tin tức thị trường (Exa Neural Search)...",
        "tool": "market_qual_search",
    })

    if not exa_configured():
        yield await _stream_sse_event("insight", {
            "text": "Exa chưa được cấu hình. Vui lòng thêm EXA_API_KEY vào .env."
        })
        yield await _stream_sse_event("complete", {"message": "Exa not configured", "tool_used": "market_qual_search"})
        return

    try:
        # Xác định loại bối cảnh từ message
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["thời tiết", "thoi tiet", "weather"]):
            context_type = "weather"
        elif any(w in msg_lower for w in ["đối thủ", "doi thu", "competitor"]):
            context_type = "competitor"
        elif any(w in msg_lower for w in ["xu hướng", "xu huong", "trend"]):
            context_type = "trend"
        elif any(w in msg_lower for w in ["vĩ mô", "vi mo", "macro", "kinh tế", "kinh te"]):
            context_type = "macro"
        else:
            context_type = "general"

        context = await get_market_context(topic=message[:200], context_type=context_type)

        articles = context.get("articles", [])
        if articles:
            yield await _stream_sse_event("data_ready", {
                "row_count": len(articles),
                "preview": [{"title": a["title"], "url": a["url"]} for a in articles[:3]],
            })

        # Format insight
        insight_parts = [f"📰 **Kết quả Tìm kiếm Tin tức (Exa)**\n"]
        for i, article in enumerate(articles, 1):
            insight_parts.append(
                f"**[{i}] {article.get('title', 'N/A')}**\n"
                f"{article.get('summary', '')}\n"
                f"Nguồn: {article.get('url', '')}\n"
            )

        if not articles:
            insight_parts.append("Không tìm được tin tức liên quan. Vui lòng kiểm tra EXA_API_KEY.")

        yield await _stream_sse_event("insight", {"text": "\n".join(insight_parts)})
        yield await _stream_sse_event("complete", {
            "message": f"Tìm thấy {len(articles)} bài báo liên quan!",
            "tool_used": "market_qual_search",
            "article_count": len(articles),
        })

    except Exception as e:
        logger.error(f"Market qual search error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi tìm kiếm tin tức: {str(e)}"})


async def _process_hybrid_revenue_drop(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Logic gộp (Hybrid): Khi phát hiện doanh thu rớt,
    tự động gọi cả TinyFish (xem đối thủ có phá giá không)
    và Exa (xem có trend gì xấu không) để đúc kết 1 insight hoàn chỉnh.
    """
    from backend.services.tinyfish_service import (
        is_configured as tf_configured,
        get_competitor_context_for_alarm,
    )
    from backend.services.exa_service import (
        is_configured as exa_configured,
        analyze_revenue_drop_context,
    )

    yield await _stream_sse_event("status", {
        "message": "🔄 Phát hiện câu hỏi về doanh thu rớt. Kích hoạt Hybrid Intelligence...",
        "tool": "hybrid_revenue_analysis",
    })

    quant_result = None
    qual_result = None

    # Bước 1: TinyFish — đối thủ có phá giá không?
    if tf_configured():
        yield await _stream_sse_event("status", {
            "message": "🔍 [1/2] Đang kiểm tra giá đối thủ (TinyFish)..."
        })
        try:
            quant_result = await get_competitor_context_for_alarm()
        except Exception as e:
            logger.warning(f"TinyFish hybrid call failed: {e}")
    else:
        yield await _stream_sse_event("status", {"message": "⚠️ TinyFish chưa cấu hình, bỏ qua bước kiểm tra giá đối thủ."})

    # Bước 2: Exa — có trend xấu hay tin tức vĩ mô không?
    if exa_configured():
        yield await _stream_sse_event("status", {
            "message": "📰 [2/2] Đang tìm kiếm bối cảnh tin tức (Exa)..."
        })
        try:
            qual_result = await analyze_revenue_drop_context()
        except Exception as e:
            logger.warning(f"Exa hybrid call failed: {e}")
    else:
        yield await _stream_sse_event("status", {"message": "⚠️ Exa chưa cấu hình, bỏ qua bước tìm kiếm tin tức."})

    # Đúc kết Hybrid Insight
    insight_parts = [
        "🔎 **Phân tích Hybrid: Tại sao Doanh thu Giảm?**\n",
        "---\n",
    ]

    # Phần 1: Kết quả TinyFish
    insight_parts.append("📊 **[TinyFish] Giá Đối thủ:**")
    if quant_result:
        competitors = quant_result.get("competitors", [])
        if competitors:
            for c in competitors[:3]:
                insight_parts.append(
                    f"- {c.get('product_name', 'N/A')}: "
                    f"{c.get('price', 'N/A')} VND "
                    f"(giảm {c.get('discount_percentage', 0)}%)"
                )
        else:
            insight_parts.append("- Không có dữ liệu đối thủ gần đây.")
    else:
        insight_parts.append("- TinyFish không khả dụng hoặc chưa cấu hình.")

    insight_parts.append("")

    # Phần 2: Kết quả Exa
    insight_parts.append("📰 **[Exa] Bối cảnh Tin tức:**")
    if qual_result:
        articles = qual_result.get("articles", [])
        if articles:
            for a in articles[:2]:
                insight_parts.append(
                    f"- **{a.get('title', 'N/A')}**\n"
                    f"  {a.get('summary', '')[:200]}"
                )
        else:
            insight_parts.append("- Không tìm được tin tức liên quan.")
    else:
        insight_parts.append("- Exa không khả dụng hoặc chưa cấu hình.")

    insight_parts.append("")
    insight_parts.append(
        "💡 **Kết luận:** Hãy kiểm tra xem đối thủ có đang đẩy mạnh khuyến mãi không và "
        "theo dõi các tin tức vĩ mô ảnh hưởng đến nhu cầu tiêu dùng."
    )

    yield await _stream_sse_event("insight", {"text": "\n".join(insight_parts)})
    yield await _stream_sse_event("complete", {
        "message": "Phân tích Hybrid hoàn thành!",
        "tool_used": "hybrid_revenue_analysis",
        "tinyfish_used": quant_result is not None,
        "exa_used": qual_result is not None,
    })


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

        # ── Intent Routing: phân loại câu hỏi và gọi đúng Tool ───────────────────────────
        # Priority: predict > dashboard > hybrid_revenue_drop > market_quant > market_qual > default
        if _is_predict_request(request.message):
            async for event in _process_predict(request.message, request.user_id):
                yield event
                try:
                    parsed = json.loads(event.split("data: ", 1)[1]) if "data: " in event else {}
                    if "text" in parsed:
                        assistant_response_parts.append(parsed["text"])
                except Exception:
                    pass

        elif _is_dashboard_request(request.message):
            async for event in _process_dashboard(request.message, request.user_id):
                yield event

        elif _is_hybrid_revenue_drop(request.message):
            # Logic gộp: doanh thu rớt → gọi cả TinyFish + Exa
            async for event in _process_hybrid_revenue_drop(request.message, request.user_id):
                yield event
                try:
                    if "data: " in event:
                        parsed = json.loads(event.split("data: ", 1)[1])
                        if "text" in parsed:
                            assistant_response_parts.append(parsed["text"])
                except Exception:
                    pass

        elif _is_market_quant_request(request.message):
            # Tool market_quant_scraper: giá đối thủ, số lượng (TinyFish)
            async for event in _process_market_quant(request.message, request.user_id):
                yield event
                try:
                    if "data: " in event:
                        parsed = json.loads(event.split("data: ", 1)[1])
                        if "text" in parsed:
                            assistant_response_parts.append(parsed["text"])
                except Exception:
                    pass

        elif _is_market_qual_request(request.message):
            # Tool market_qual_search: tin tức, bối cảnh, lý do (Exa)
            async for event in _process_market_qual(request.message, request.user_id):
                yield event
                try:
                    if "data: " in event:
                        parsed = json.loads(event.split("data: ", 1)[1])
                        if "text" in parsed:
                            assistant_response_parts.append(parsed["text"])
                except Exception:
                    pass

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
