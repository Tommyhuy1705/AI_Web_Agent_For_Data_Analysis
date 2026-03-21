"""
Chat Router
Nhận text từ Frontend, phân loại intent, và stream kết quả về qua SSE.

Intent Routing Priority (cao → thấp):
1. predict          → ML time-series forecast
2. dashboard        → multi-chart dashboard
3. hybrid_drop      → doanh thu rớt → TinyFish + Exa
4. market_quant     → giá đối thủ, số lượng → TinyFish crawl
5. market_qual      → tin tức, xu hướng, lý do → Exa search
6. market_outside   → câu hỏi thị trường ngoài DB → Exa fallback
7. default          → Text-to-SQL → chart → insight (LLM trực tiếp)

LLM: DashScope/Qwen (primary) → OpenAI (fallback)
Market Intelligence: TinyFish (quantitative) + Exa (qualitative/semantic)
"""

import asyncio
import json
import logging
import os
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

# ============================================================
# Schema & Guardrail Prompts
# ============================================================

SCHEMA_FALLBACK_SUMMARY = """Read-only analytics schema:
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

If the question is NOT about internal database data (e.g. external market, competitors, news, trends),
return EXACTLY this string (no SQL):
OUTSIDE_DB"""

# ============================================================
# Intent Detection Keywords
# ============================================================

PREDICT_KEYWORDS = [
    "dự đoán", "du doan", "forecast", "predict", "xu hướng tương lai",
    "dự báo", "du bao", "prediction", "tương lai", "tuong lai",
    "next month", "tháng tới", "thang toi", "quý tới", "quy toi",
    "năm tới", "nam toi", "sắp tới", "sap toi",
]

DASHBOARD_KEYWORDS = [
    "tạo dashboard", "tao dashboard", "dashboard tổng quan", "dashboard tong quan",
    "build dashboard", "create dashboard", "make dashboard",
    "dashboard theo dõi", "dashboard theo doi",
    "bảng điều khiển", "bang dieu khien",
    "tổng quan dashboard", "tong quan dashboard",
    "dashboard doanh thu", "dashboard don hang",
    "dashboard đơn hàng",
]

# Tool market_quant_scraper (TinyFish) — giá đối thủ, số lượng cụ thể
MARKET_QUANT_KEYWORDS = [
    # Giá đối thủ
    "giá đối thủ", "gia doi thu", "competitor price", "đối thủ bán giá",
    "giá shopee", "gia shopee", "giá lazada", "gia lazada", "giá tiki", "gia tiki",
    "so sánh giá", "so sanh gia", "price comparison",
    # Số lượng bán
    "số lượng bán", "so luong ban", "items sold", "đã bán", "da ban",
    # Giảm giá đối thủ
    "giảm giá đối thủ", "giam gia doi thu", "discount competitor",
    "phần trăm giảm", "phan tram giam", "% giảm",
    # Crawl / scrape
    "cào dữ liệu", "cao du lieu", "crawl", "scrape", "market intel",
    "tình báo thị trường", "tinh bao thi truong",
]

# Tool market_qual_search (Exa) — tin tức, bối cảnh, lý do
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
    # Phân tích thị trường
    "phân tích thị trường", "phan tich thi truong", "market analysis",
    "thị trường", "thi truong", "ngành", "nganh", "industry",
    # Đối thủ cạnh tranh (định tính)
    "đối thủ cạnh tranh", "doi thu canh tranh", "competitor analysis",
    "cạnh tranh", "canh tranh", "competitive",
]

# Hybrid trigger — doanh thu rớt → TinyFish + Exa
HYBRID_REVENUE_DROP_KEYWORDS = [
    "doanh thu giảm", "doanh thu rot", "doanh thu rớt", "revenue drop",
    "revenue decline", "doanh thu xuống", "doanh thu xuong",
    "doanh số giảm", "doanh so giam", "sales drop", "sales decline",
    "tại sao doanh thu", "tai sao doanh thu", "why revenue",
    "doanh thu thấp", "doanh thu thap", "revenue low",
]

# Câu hỏi thị trường bên ngoài DB — fallback sang Exa
MARKET_OUTSIDE_DB_KEYWORDS = [
    # Thị trường tổng quát
    "thị trường", "thi truong", "market", "ngành hàng", "nganh hang",
    # Phân tích ngoài
    "phân tích thị trường", "phan tich thi truong",
    "tình hình thị trường", "tinh hinh thi truong",
    "thị phần", "thi phan", "market share",
    # Đối thủ (định tính)
    "đối thủ cạnh tranh", "doi thu canh tranh",
    "cạnh tranh", "canh tranh", "competitive landscape",
    # Người tiêu dùng / hành vi
    "hành vi người tiêu dùng", "hanh vi nguoi tieu dung",
    "consumer behavior", "customer insight",
    # Kinh tế / vĩ mô
    "kinh tế vĩ mô", "kinh te vi mo", "macroeconomic",
    "lạm phát", "lam phat", "inflation",
    "lãi suất", "lai suat", "interest rate",
    # Ngành cụ thể
    "bán lẻ", "ban le", "retail", "thương mại điện tử", "thuong mai dien tu",
    "e-commerce", "ecommerce",
    # Xu hướng
    "xu hướng ngành", "xu huong nganh", "industry trend",
    "xu hướng tiêu dùng", "xu huong tieu dung",
]

# Pre-defined dashboard queries
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


# ============================================================
# Request Models
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message/question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    user_id: str = Field(default="default_user", description="User identifier")
    session_id: Optional[str] = Field(None, description="Chat session ID for history & context memory")


class ChatMessage(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


# ============================================================
# Helpers
# ============================================================

async def _stream_sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _friendly_ai_overload_message() -> str:
    return "The AI service is currently overloaded. Please try again in a few seconds."


async def _build_tinyfish_dashboard_chart() -> Optional[Dict[str, Any]]:
    """Create a lightweight dashboard chart from latest TinyFish competitor data."""
    try:
        rows = await execute_safe_query(
            "SELECT keyword, AVG(price) AS avg_price, AVG(discount_pct) AS avg_discount, "
            "AVG(sold_count) AS avg_sold, COUNT(*) AS sample_size "
            "FROM competitor_prices "
            "WHERE crawled_at >= NOW() - INTERVAL '14 days' "
            "GROUP BY keyword "
            "ORDER BY avg_price DESC "
            "LIMIT 10"
        )
        if not rows:
            return None

        return {
            "chart_type": "bar",
            "title": "Competitor Pricing Snapshot (TinyFish)",
            "description": "Average competitor price by tracked keyword in the last 14 days",
            "config": {
                "xAxis": {"dataKey": "keyword", "label": "Keyword"},
                "yAxis": {"label": "Average Price (VND)"},
                "series": [
                    {"dataKey": "avg_price", "name": "Avg Price", "color": "#3B82F6"},
                    {"dataKey": "avg_discount", "name": "Avg Discount %", "color": "#10B981"},
                    {"dataKey": "avg_sold", "name": "Avg Sold Count", "color": "#F59E0B"},
                ],
            },
            "data": rows,
            "dashboard_panel": "tinyfish_competitor_stats",
        }
    except Exception as e:
        logger.warning(f"Failed to build TinyFish dashboard chart: {e}")
        return None


# ============================================================
# Intent Detection Functions
# ============================================================

def _is_predict_request(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in PREDICT_KEYWORDS)


def _is_dashboard_request(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in DASHBOARD_KEYWORDS)


def _is_market_quant_request(message: str) -> bool:
    """TinyFish: câu hỏi về con số cụ thể của đối thủ."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in MARKET_QUANT_KEYWORDS)


def _is_market_qual_request(message: str) -> bool:
    """Exa: câu hỏi về tin tức, bối cảnh, lý do biến động."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in MARKET_QUAL_KEYWORDS)


def _is_hybrid_revenue_drop(message: str) -> bool:
    """Hybrid: doanh thu rớt → TinyFish + Exa."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in HYBRID_REVENUE_DROP_KEYWORDS)


def _is_market_outside_db(message: str) -> bool:
    """
    Phát hiện câu hỏi về thị trường bên ngoài phạm vi DB nội bộ.
    Dùng làm fallback trước khi chạy Text-to-SQL.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in MARKET_OUTSIDE_DB_KEYWORDS)


def _build_fallback_chart(dq: dict, data: list) -> Optional[dict]:
    if not data:
        return None
    keys = list(data[0].keys())
    numeric_keys = [k for k in keys if isinstance(data[0].get(k), (int, float))]
    text_keys = [k for k in keys if not isinstance(data[0].get(k), (int, float))]
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
    series = [
        {"dataKey": nk, "name": nk.replace("_", " ").title(), "color": colors[i % len(colors)]}
        for i, nk in enumerate(numeric_keys[:3])
    ]
    config: Dict[str, Any] = {
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
    if chart_type == "pie" and text_keys and numeric_keys:
        config["config"]["nameKey"] = text_keys[0]
        config["config"]["dataKey"] = numeric_keys[0]
    return config


# ============================================================
# Process Functions
# ============================================================

async def _process_market_quant(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Tool: market_quant_scraper (TinyFish) — cào giá đối thủ."""
    from backend.services.tinyfish_service import (
        is_configured as tf_configured,
        run_competitor_crawl,
        get_market_intel_summary,
    )

    yield await _stream_sse_event("status", {
        "message": "Running quantitative crawl from TinyFish (Shopee/Tiki) ...",
        "tool": "market_quant_scraper",
    })

    if not tf_configured():
        yield await _stream_sse_event("insight", {
            "text": "TinyFish is not configured. Please set TINYFISH_API_KEY in environment settings."
        })
        yield await _stream_sse_event("complete", {"message": "TinyFish not configured", "tool_used": "market_quant_scraper"})
        return

    try:
        yield await _stream_sse_event("status", {"message": "Crawling competitor data (this can take 30-60 seconds) ..."})
        await run_competitor_crawl()
        summary = await get_market_intel_summary()
        chart_payload = await _build_tinyfish_dashboard_chart()

        if summary:
            yield await _stream_sse_event("data_ready", {
                "row_count": summary.get("total_records", 0),
                "preview": summary.get("recent_crawls", [])[:5],
            })
            if chart_payload:
                yield await _stream_sse_event("chart", chart_payload)
            insight_text = (
                f"Quantitative crawl completed.\n\n"
                f"- Total records: {summary.get('total_records', 0)}\n"
                f"- Sources: {', '.join(summary.get('sources', [])) or 'N/A'}\n"
                f"- Last crawl: {summary.get('last_crawled_at', 'N/A')}\n\n"
                f"Output type: dashboard-ready statistics from TinyFish competitor data. "
                f"Ask for product-level comparisons if you want deeper drill-down."
            )
        else:
            insight_text = "Quantitative crawl completed. Data is stored in raw_market_intel for dashboard analytics."

        yield await _stream_sse_event("insight", {"text": insight_text})
        yield await _stream_sse_event("complete", {
            "message": "TinyFish quantitative crawl completed.",
            "tool_used": "market_quant_scraper",
            "output_type": "dashboard_statistics",
        })

    except Exception as e:
        logger.error(f"Market quant scraper error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi cào dữ liệu: {str(e)}"})


async def _process_market_qual(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Tool: market_qual_search (Exa) — tìm tin tức, bối cảnh, lý do."""
    from backend.services.exa_service import (
        is_configured as exa_configured,
        get_market_context,
    )

    yield await _stream_sse_event("status", {
        "message": "Searching qualitative market news with Exa Neural Search ...",
        "tool": "market_qual_search",
    })

    if not exa_configured():
        yield await _stream_sse_event("insight", {
            "text": "Exa is not configured. Please set EXA_API_KEY in environment settings."
        })
        yield await _stream_sse_event("complete", {"message": "Exa not configured", "tool_used": "market_qual_search"})
        return

    try:
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["thời tiết", "thoi tiet", "weather"]):
            context_type = "weather"
        elif any(w in msg_lower for w in ["đối thủ", "doi thu", "competitor", "cạnh tranh", "canh tranh"]):
            context_type = "competitor"
        elif any(w in msg_lower for w in ["xu hướng", "xu huong", "trend", "ngành", "nganh"]):
            context_type = "trend"
        elif any(w in msg_lower for w in ["vĩ mô", "vi mo", "macro", "kinh tế", "kinh te", "lạm phát", "lam phat"]):
            context_type = "macro"
        else:
            context_type = "general"

        context = await get_market_context(topic=message[:300], context_type=context_type)
        articles = context.get("articles", [])

        if articles:
            yield await _stream_sse_event("data_ready", {
                "row_count": len(articles),
                "preview": [{"title": a["title"], "url": a["url"]} for a in articles[:3]],
            })

        insight_parts = ["News intelligence result (Exa):\n"]
        for i, article in enumerate(articles, 1):
            title = article.get("title", "N/A")
            summary = article.get("summary", "")
            url = article.get("url", "")
            pub_date = article.get("published_date", "")
            insight_parts.append(
                f"[{i}] {title}\n"
                f"{summary[:400]}\n"
                f"Source: {url}"
                + (f"\nPublished: {pub_date[:10]}" if pub_date else "")
                + "\n"
            )

        if not articles:
            insight_parts.append(
                "No relevant news was found. Try a more specific market topic or competitor name."
            )

        yield await _stream_sse_event("insight", {"text": "\n".join(insight_parts)})
        yield await _stream_sse_event("complete", {
            "message": f"Found {len(articles)} relevant market sources.",
            "tool_used": "market_qual_search",
            "article_count": len(articles),
            "output_type": "news_sources",
        })

    except Exception as e:
        logger.error(f"Market qual search error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi tìm kiếm tin tức: {str(e)}"})


async def _process_hybrid_revenue_drop(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Hybrid: doanh thu rớt → TinyFish (giá đối thủ) + Exa (tin tức) → 1 insight hoàn chỉnh.
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
        "message": "Revenue-drop intent detected. Starting hybrid intelligence workflow ...",
        "tool": "hybrid_revenue_analysis",
    })

    quant_result = None
    qual_result = None

    if tf_configured():
        yield await _stream_sse_event("status", {"message": "[1/2] Fetching quantitative competitor signals from TinyFish ..."})
        try:
            quant_result = await get_competitor_context_for_alarm()
        except Exception as e:
            logger.warning(f"TinyFish hybrid call failed: {e}")
    else:
        yield await _stream_sse_event("status", {"message": "TinyFish is not configured, skipping quantitative competitor signals."})

    if exa_configured():
        yield await _stream_sse_event("status", {"message": "[2/2] Fetching qualitative market context from Exa ..."})
        try:
            qual_result = await analyze_revenue_drop_context()
        except Exception as e:
            logger.warning(f"Exa hybrid call failed: {e}")
    else:
        yield await _stream_sse_event("status", {"message": "Exa is not configured, skipping qualitative news context."})

    insight_parts = ["Hybrid Revenue Drop Analysis", ""]

    insight_parts.append("[TinyFish] Quantitative competitor metrics:")
    if quant_result:
        competitors = quant_result.get("competitors", [])
        if competitors:
            for c in competitors[:3]:
                insight_parts.append(
                    f"- {c.get('product_name', 'N/A')}: "
                    f"{c.get('price', 'N/A')} VND "
                    f"(discount {c.get('discount_percentage', 0)}%)"
                )
        else:
            insight_parts.append("- No recent competitor records found.")
    else:
        insight_parts.append("- TinyFish unavailable or not configured.")

    insight_parts.append("")
    insight_parts.append("[Exa] Qualitative news context:")
    if qual_result:
        articles = qual_result.get("articles", [])
        if articles:
            for a in articles[:2]:
                insight_parts.append(
                    f"- **{a.get('title', 'N/A')}**\n"
                    f"  {a.get('summary', '')[:250]}"
                )
        else:
            insight_parts.append("- No relevant news sources found.")
    else:
        insight_parts.append("- Exa unavailable or not configured.")

    insight_parts.append("")
    insight_parts.append(
        "Conclusion: monitor competitor discount pressure and track macro news that can impact consumer demand."
    )

    yield await _stream_sse_event("insight", {"text": "\n".join(insight_parts)})
    yield await _stream_sse_event("complete", {
        "message": "Hybrid analysis completed.",
        "tool_used": "hybrid_revenue_analysis",
        "tinyfish_used": quant_result is not None,
        "exa_used": qual_result is not None,
    })


async def _process_market_outside_db(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """
    Fallback: câu hỏi thị trường bên ngoài DB → Exa semantic search.
    Được gọi khi LLM trả về OUTSIDE_DB hoặc keyword detection phát hiện câu hỏi ngoài DB.
    """
    from backend.services.exa_service import (
        is_configured as exa_configured,
        search_outside_db,
    )

    yield await _stream_sse_event("status", {
        "message": "Question detected outside internal DB scope. Searching market intelligence via Exa ...",
        "tool": "market_outside_db_search",
    })

    if not exa_configured():
        # Fallback: dùng LLM để trả lời từ kiến thức chung
        yield await _stream_sse_event("status", {
            "message": "Exa is not configured. Falling back to general LLM response ..."
        })
        async for event in _process_llm_general(message, user_id):
            yield event
        return

    try:
        result = await search_outside_db(user_question=message)
        articles = result.get("articles", [])

        if articles:
            yield await _stream_sse_event("data_ready", {
                "row_count": len(articles),
                "preview": [{"title": a["title"], "url": a["url"]} for a in articles[:3]],
            })

        formatted_answer = result.get("formatted_answer", "")

        # Nếu có kết quả, dùng LLM để tổng hợp insight từ các bài báo
        if articles and is_configured():
            yield await _stream_sse_event("status", {"message": "Synthesizing cross-source market insight ..."})
            try:
                articles_text = "\n".join([
                    f"- {a.get('title', '')}: {a.get('summary', '')[:300]}"
                    for a in articles[:4]
                ])
                synthesis = await chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a market intelligence analyst. "
                                "Synthesize the provided sources into concise English (max 300 words). "
                                "Focus on practical business insight, risks, and opportunities."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Question: {message}\n\n"
                                f"Relevant sources:\n{articles_text}\n\n"
                                f"Write a concise synthesis:"
                            ),
                        },
                    ],
                    temperature=0.4,
                    max_tokens=600,
                )
                formatted_answer = (
                    formatted_answer
                    + "\n\n---\nSynthesis:\n"
                    + synthesis
                )
            except Exception as e:
                logger.warning(f"LLM synthesis failed: {e}")

        yield await _stream_sse_event("insight", {"text": formatted_answer})
        yield await _stream_sse_event("complete", {
            "message": f"Found {len(articles)} market sources.",
            "tool_used": "market_outside_db_search",
            "article_count": len(articles),
        })

    except Exception as e:
        logger.error(f"Market outside DB search error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi tìm kiếm thị trường: {str(e)}"})


async def _process_llm_general(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Trả lời câu hỏi chung bằng LLM (không có DB, không có Exa)."""
    if not is_configured():
        yield await _stream_sse_event("error", {
            "message": "No LLM provider configured. Please set DASHSCOPE_API_KEY or OPENAI_API_KEY."
        })
        return

    try:
        response = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an intelligent business analytics assistant. "
                        "Always answer in clear English with concise, practical recommendations."
                    ),
                },
                {"role": "user", "content": message},
            ],
            temperature=0.5,
            max_tokens=800,
        )
        yield await _stream_sse_event("insight", {"text": response})
        yield await _stream_sse_event("complete", {
            "message": "Completed.",
            "tool_used": "llm_general",
        })
    except Exception as e:
        logger.error(f"LLM general error: {e}", exc_info=True)
        yield await _stream_sse_event("error", {"message": f"Lỗi LLM: {str(e)}"})


async def _process_dashboard(
    message: str,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Tạo dashboard multi-chart từ các pre-defined queries."""
    yield await _stream_sse_event("status", {"message": "Đang tạo dashboard tổng quan..."})

    try:
        all_charts = []
        all_sqls = []
        failed_panels = []

        for i, dq in enumerate(DASHBOARD_QUERIES):
            yield await _stream_sse_event("status", {
                "message": f"Đang truy vấn: {dq['title']} ({i+1}/{len(DASHBOARD_QUERIES)})..."
            })
            try:
                data = await execute_safe_query(dq["sql"])
            except Exception as e:
                logger.warning(f"Dashboard query failed for {dq['name']}: {e}")
                failed_panels.append({"name": dq["name"], "title": dq["title"], "error": str(e)})
                continue

            if not data:
                continue

            all_sqls.append({"name": dq["name"], "sql": dq["sql"]})
            yield await _stream_sse_event("status", {"message": f"Đang tạo biểu đồ: {dq['title']}..."})

            try:
                chart_config = await generate_chart_config(data, dq["chart_hint"])
                chart_config["title"] = dq["title"]
                chart_config["dashboard_panel"] = dq["name"]
                chart_config["data"] = data[:100]
                all_charts.append(chart_config)
            except Exception as e:
                logger.warning(f"LLM chart generation failed for {dq['name']}: {e}, using fallback")
                fallback = _build_fallback_chart(dq, data)
                if fallback:
                    all_charts.append(fallback)

        yield await _stream_sse_event("sql_generated", {
            "sql": "\n\n".join([f"-- {s['name']}\n{s['sql']}" for s in all_sqls]),
            "tool_used": "dashboard_builder",
            "queries": all_sqls,
        })
        yield await _stream_sse_event("data_ready", {
            "row_count": sum(len(c.get("data", [])) for c in all_charts),
            "panel_count": len(all_charts),
            "preview": [{"panel": c.get("dashboard_panel"), "title": c.get("title")} for c in all_charts],
        })

        for chart in all_charts:
            yield await _stream_sse_event("chart", chart)

        yield await _stream_sse_event("status", {"message": "Đang phân tích insight tổng quan..."})
        try:
            summary_parts = [
                f"{chart.get('title', '')}: {len(chart.get('data', []))} records"
                for chart in all_charts if chart.get("data")
            ]
            insight = await generate_insight_summary(
                [{"dashboard_panels": len(all_charts), "summaries": summary_parts}],
                f"Tổng quan dashboard: {message}"
            )
        except Exception:
            insight = f"Dashboard tổng quan với {len(all_charts)} biểu đồ đã được tạo thành công."

        if failed_panels:
            failed_info = ", ".join([p["title"] for p in failed_panels])
            insight += f"\n\nLưu ý: Một số panel không thể tải dữ liệu ({failed_info})."

        yield await _stream_sse_event("insight", {"text": insight})
        complete_msg = (
            f"Dashboard hoàn thành! {len(all_charts)} biểu đồ đã được tạo."
            if all_charts
            else "Không thể tạo dashboard do không truy vấn được dữ liệu."
        )
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
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Dự đoán doanh thu bằng ML time-series."""
    from backend.ml_models.time_series import predict_revenue, generate_strategic_insight

    yield await _stream_sse_event("status", {"message": "Đang phân tích xu hướng và dự đoán..."})

    try:
        yield await _stream_sse_event("sql_generated", {
            "sql": "SELECT month, total_revenue FROM v_monthly_revenue ORDER BY month",
            "tool_used": "predict_revenue"
        })
        yield await _stream_sse_event("status", {"message": "Đang chạy mô hình dự đoán..."})
        predictions = await predict_revenue(periods=3)

        historical_data = await execute_safe_query(
            "SELECT month, total_revenue FROM v_monthly_revenue ORDER BY month"
        )

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


async def _process_direct(
    message: str,
    user_id: str,
    context_messages: Optional[List[Dict]] = None,
) -> AsyncGenerator[str, None]:
    """
    Text-to-SQL với LLM trực tiếp (Qwen/OpenAI).
    Nếu LLM trả về OUTSIDE_DB → chuyển sang Exa market search.
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
        # Build messages with context
        messages: List[Dict] = [
            {
                "role": "system",
                "content": SQL_SYSTEM_PROMPT.format(guardrail=READ_ONLY_GUARDRAIL)
            }
        ]
        if context_messages:
            messages.extend(context_messages[-6:])  # Tối đa 6 messages context
        messages.append({"role": "user", "content": message})

        sql_query = await chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=500,
        )

        sql_query = sql_query.strip()
        if sql_query.startswith("```"):
            sql_query = sql_query.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        # ── Fallback: LLM nhận ra câu hỏi ngoài DB ──────────────────────────
        if "OUTSIDE_DB" in sql_query:
            logger.info(f"LLM detected outside-DB question: {message[:80]}")
            yield await _stream_sse_event("status", {
                "message": "🌐 Câu hỏi ngoài phạm vi DB. Chuyển sang tìm kiếm thị trường (Exa)..."
            })
            async for event in _process_market_outside_db(message, user_id):
                yield event
            return

        yield await _stream_sse_event("sql_generated", {"sql": sql_query})
        yield await _stream_sse_event("status", {"message": "Đang truy vấn dữ liệu..."})

        data = await execute_safe_query(sql_query)

        yield await _stream_sse_event("data_ready", {
            "row_count": len(data),
            "preview": data[:5] if data else [],
        })

        yield await _stream_sse_event("status", {"message": "Đang tạo biểu đồ..."})
        chart_config = await generate_chart_config(data, message)
        yield await _stream_sse_event("chart", chart_config)

        yield await _stream_sse_event("status", {"message": "Đang phân tích insight..."})
        insight = await generate_insight_summary(data, message)
        yield await _stream_sse_event("insight", {"text": insight})

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


# ============================================================
# Main Chat Stream Endpoint
# ============================================================

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Chat endpoint với SSE streaming.
    Intent Routing Priority: predict > dashboard > hybrid_drop > market_quant > market_qual > market_outside_db > default(SQL)
    """
    logger.info(f"Chat request from {request.user_id}: {request.message[:100]}...")

    async def event_generator():
        from backend.services.chat_history_service import (
            create_session, save_message, get_context_messages, auto_generate_title
        )

        # ── Session management ──────────────────────────────────────────────
        session_id = request.session_id
        is_new_session = False
        if not session_id:
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

        # Lưu user message
        try:
            await save_message(
                session_id=session_id,
                role="user",
                content=request.message,
                metadata={"message_id": message_id},
            )
            if is_new_session:
                asyncio.create_task(auto_generate_title(session_id, request.message))
        except Exception as e:
            logger.warning(f"Failed to save user message: {e}")

        # Lấy context history
        context_messages = []
        try:
            context_messages = await get_context_messages(session_id)
            if context_messages and context_messages[-1].get("content") == request.message:
                context_messages = context_messages[:-1]
        except Exception as e:
            logger.warning(f"Failed to get context messages: {e}")

        # ── Collect assistant response ──────────────────────────────────────
        assistant_response_parts = []

        def _collect(event_str: str):
            try:
                if "data: " in event_str:
                    parsed = json.loads(event_str.split("data: ", 1)[1])
                    if "text" in parsed:
                        assistant_response_parts.append(parsed["text"])
            except Exception:
                pass

        # ── Intent Routing ──────────────────────────────────────────────────
        # Priority: predict > dashboard > hybrid_drop > market_quant > market_qual > market_outside_db > default
        if _is_predict_request(request.message):
            async for event in _process_predict(request.message, request.user_id):
                yield event
                _collect(event)

        elif _is_dashboard_request(request.message):
            async for event in _process_dashboard(request.message, request.user_id):
                yield event

        elif _is_hybrid_revenue_drop(request.message):
            async for event in _process_hybrid_revenue_drop(request.message, request.user_id):
                yield event
                _collect(event)

        elif _is_market_quant_request(request.message):
            async for event in _process_market_quant(request.message, request.user_id):
                yield event
                _collect(event)

        elif _is_market_qual_request(request.message):
            async for event in _process_market_qual(request.message, request.user_id):
                yield event
                _collect(event)

        elif _is_market_outside_db(request.message):
            # Câu hỏi thị trường bên ngoài DB → Exa semantic search
            async for event in _process_market_outside_db(request.message, request.user_id):
                yield event
                _collect(event)

        else:
            # Default: Text-to-SQL với LLM (có fallback OUTSIDE_DB → Exa)
            async for event in _process_direct(
                message=request.message,
                user_id=request.user_id,
                context_messages=context_messages,
            ):
                yield event
                _collect(event)

        # Lưu assistant response
        if assistant_response_parts:
            assistant_content = " ".join(assistant_response_parts)
            try:
                await save_message(
                    session_id=session_id,
                    role="assistant",
                    content=assistant_content[:4000],
                    metadata={"message_id": message_id},
                )
            except Exception as e:
                logger.warning(f"Failed to save assistant message: {e}")

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


# ============================================================
# Non-streaming Query Endpoint (for testing)
# ============================================================

@router.post("/query")
async def chat_query(request: ChatRequest):
    """Chat endpoint không streaming (cho testing)."""
    logger.info(f"Query request from {request.user_id}: {request.message[:100]}...")

    try:
        if not is_configured():
            raise HTTPException(status_code=500, detail="No LLM provider configured")

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

        if _is_hybrid_revenue_drop(request.message):
            from backend.services.tinyfish_service import is_configured as tf_configured, get_competitor_context_for_alarm
            from backend.services.exa_service import is_configured as exa_configured, analyze_revenue_drop_context
            quant = await get_competitor_context_for_alarm() if tf_configured() else None
            qual = await analyze_revenue_drop_context() if exa_configured() else None
            return {
                "success": True,
                "tool_used": "hybrid_revenue_analysis",
                "tinyfish_result": quant,
                "exa_result": qual,
            }

        if _is_market_qual_request(request.message) or _is_market_outside_db(request.message):
            from backend.services.exa_service import is_configured as exa_configured, search_outside_db
            if exa_configured():
                result = await search_outside_db(request.message)
                return {"success": True, "tool_used": "market_qual_search", **result}

        # Default: Text-to-SQL
        sql = await chat_completion(
            messages=[
                {"role": "system", "content": SQL_SYSTEM_PROMPT.format(guardrail=READ_ONLY_GUARDRAIL)},
                {"role": "user", "content": request.message},
            ],
            temperature=0.1,
        )
        sql = sql.strip()
        if sql.startswith("```"):
            sql = sql.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        if "OUTSIDE_DB" in sql:
            from backend.services.exa_service import is_configured as exa_configured, search_outside_db
            if exa_configured():
                result = await search_outside_db(request.message)
                return {"success": True, "tool_used": "market_outside_db_search", **result}
            return {"success": False, "message": "Câu hỏi ngoài phạm vi dữ liệu nội bộ và Exa chưa được cấu hình."}

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
