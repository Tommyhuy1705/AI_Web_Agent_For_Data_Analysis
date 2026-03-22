"""
Dashboard Router
Cung cấp API cho trang Dashboard tĩnh.
Trả về tất cả dữ liệu cần thiết cho grid biểu đồ trong một request.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.services.db_executor import execute_safe_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


async def _fetch_all_fact_sales(page_size: int = 1000) -> list[dict]:
    """Fetch all fact_sales rows via pagination to bypass Supabase max rows limit."""
    all_rows: list[dict] = []
    offset = 0
    while True:
        rows = await execute_safe_query(f"""
            SELECT sale_id, total_amount, customer_id, product_id, channel
            FROM public.fact_sales
            ORDER BY sale_id ASC
            LIMIT {page_size}
            OFFSET {offset}
        """)
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows


@router.get("/data")
async def get_dashboard_data() -> Dict[str, Any]:
    """
    Lấy toàn bộ dữ liệu cho Dashboard.
    Gọi nhiều query song song để tối ưu tốc độ.
    """
    import asyncio

    try:
        # Chạy tất cả queries song song
        results = await asyncio.gather(
            _get_revenue_summary(),
            _get_monthly_revenue(),
            _get_top_products(),
            _get_customer_segments(),
            _get_daily_revenue_trend(),
            _get_channel_distribution(),
            _get_competitor_overview(),
            return_exceptions=True,
        )

        # Xử lý kết quả
        keys = [
            "revenue_summary",
            "monthly_revenue",
            "top_products",
            "customer_segments",
            "daily_revenue",
            "channel_distribution",
            "competitor_overview",
        ]

        dashboard_data: Dict[str, Any] = {}
        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                logger.error(f"Dashboard query error ({key}): {result}")
                dashboard_data[key] = {"error": str(result), "data": []}
            else:
                dashboard_data[key] = result

        return {
            "success": True,
            "data": dashboard_data,
        }

    except Exception as e:
        logger.error(f"Dashboard data error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _get_revenue_summary() -> Dict[str, Any]:
    """KPI tổng quan: Tổng doanh thu, số đơn, giá trị trung bình."""
    data = await _fetch_all_fact_sales()
    # Compute aggregates in Python since PostgREST doesn't support aggregate functions
    total_orders = len(data)
    total_revenue = sum(float(r.get("total_amount", 0)) for r in data)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
    total_customers = len(set(r.get("customer_id") for r in data if r.get("customer_id")))
    total_products = len(set(r.get("product_id") for r in data if r.get("product_id")))
    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "avg_order_value": round(avg_order_value, 0),
        "total_customers": total_customers,
        "total_products": total_products,
    }


async def _get_monthly_revenue() -> Dict[str, Any]:
    """Doanh thu theo tháng - Line chart."""
    data = await execute_safe_query("""
        SELECT month, total_orders, total_revenue, avg_order_value
        FROM public.v_monthly_revenue
        ORDER BY month ASC
    """)
    return {
        "chart_type": "line",
        "title": "Doanh thu theo tháng",
        "config": {
            "xAxis": {"dataKey": "month", "label": "Tháng"},
            "series": [
                {"dataKey": "total_revenue", "name": "Doanh thu", "color": "#3B82F6"}
            ],
        },
        "data": data,
    }


async def _get_top_products() -> Dict[str, Any]:
    """Top 10 sản phẩm bán chạy - Bar chart."""
    data = await execute_safe_query("""
        SELECT product_name, category, total_orders, total_revenue
        FROM public.v_product_performance
        ORDER BY total_revenue DESC
        LIMIT 10
    """)
    return {
        "chart_type": "bar",
        "title": "Top 10 sản phẩm theo doanh thu",
        "config": {
            "xAxis": {"dataKey": "product_name", "label": "Sản phẩm"},
            "series": [
                {"dataKey": "total_revenue", "name": "Doanh thu", "color": "#10B981"}
            ],
        },
        "data": data,
    }


async def _get_customer_segments() -> Dict[str, Any]:
    """Phân bố doanh thu theo phân khúc khách hàng - Pie chart."""
    data = await execute_safe_query("""
        SELECT segment, total_customers, total_orders, total_revenue
        FROM public.v_customer_segment_revenue
        ORDER BY total_revenue DESC
    """)
    # Aggregate by segment in Python since PostgREST doesn't support GROUP BY
    segment_map: Dict[str, Dict] = {}
    for row in data:
        seg = row.get("segment", "Unknown")
        if seg not in segment_map:
            segment_map[seg] = {"segment": seg, "total_revenue": 0, "total_orders": 0}
        segment_map[seg]["total_revenue"] += float(row.get("total_revenue", 0))
        segment_map[seg]["total_orders"] += int(row.get("total_orders", 0))
    aggregated = sorted(segment_map.values(), key=lambda x: x["total_revenue"], reverse=True)
    return {
        "chart_type": "pie",
        "title": "Doanh thu theo phân khúc khách hàng",
        "config": {
            "nameKey": "segment",
            "dataKey": "total_revenue",
        },
        "data": aggregated,
    }


async def _get_daily_revenue_trend() -> Dict[str, Any]:
    """Doanh thu 30 ngày gần nhất - Area chart."""
    data = await execute_safe_query("""
        SELECT order_date, total_orders, total_revenue
        FROM public.v_daily_revenue
        ORDER BY order_date DESC
        LIMIT 30
    """)
    # Reverse to show chronological order
    data.reverse()
    return {
        "chart_type": "area",
        "title": "Doanh thu 30 ngày gần nhất",
        "config": {
            "xAxis": {"dataKey": "order_date", "label": "Ngày"},
            "series": [
                {"dataKey": "total_revenue", "name": "Doanh thu", "color": "#8B5CF6"}
            ],
        },
        "data": data,
    }


async def _get_channel_distribution() -> Dict[str, Any]:
    """Phân bố doanh thu theo kênh bán hàng - Bar chart."""
    data = await _fetch_all_fact_sales()
    # Aggregate by channel in Python since PostgREST doesn't support GROUP BY
    channel_map: Dict[str, Dict] = {}
    for row in data:
        ch = row.get("channel", "Unknown")
        if ch not in channel_map:
            channel_map[ch] = {"channel": ch, "total_orders": 0, "total_revenue": 0}
        channel_map[ch]["total_orders"] += 1
        channel_map[ch]["total_revenue"] += float(row.get("total_amount", 0))
    aggregated = sorted(channel_map.values(), key=lambda x: x["total_revenue"], reverse=True)
    return {
        "chart_type": "bar",
        "title": "Doanh thu theo kênh bán hàng",
        "config": {
            "xAxis": {"dataKey": "channel", "label": "Kênh"},
            "series": [
                {"dataKey": "total_revenue", "name": "Doanh thu", "color": "#F59E0B"},
                {"dataKey": "total_orders", "name": "Số đơn", "color": "#EF4444"},
            ],
        },
        "data": aggregated,
    }


async def _get_competitor_overview() -> Dict[str, Any]:
    """Tổng quan giá đối thủ cạnh tranh - Bar chart (từ TinyFish data)."""
    try:
        data = await execute_safe_query("""
            SELECT source, keyword, product_name, price, discount_pct, sold_count, rating
            FROM public.competitor_prices
            ORDER BY crawled_at DESC
            LIMIT 20
        """)

        if not data:
            return {
                "chart_type": "bar",
                "title": "Đối thủ cạnh tranh (TinyFish Market Intel)",
                "description": "Chưa có dữ liệu. Hãy chạy Market Intel Crawl trước.",
                "config": {
                    "xAxis": {"dataKey": "product_name", "label": "Sản phẩm"},
                    "series": [
                        {"dataKey": "price", "name": "Giá bán", "color": "#EF4444"},
                    ],
                },
                "data": [],
            }

        # Truncate long product names for chart display
        for item in data:
            name = item.get("product_name", "")
            if len(name) > 30:
                item["product_name"] = name[:27] + "..."

        return {
            "chart_type": "bar",
            "title": "Đối thủ cạnh tranh (TinyFish Market Intel)",
            "description": f"Top {len(data)} sản phẩm đối thủ gần nhất",
            "config": {
                "xAxis": {"dataKey": "product_name", "label": "Sản phẩm đối thủ"},
                "series": [
                    {"dataKey": "price", "name": "Giá bán (VNĐ)", "color": "#EF4444"},
                    {"dataKey": "discount_pct", "name": "Giảm giá (%)", "color": "#F59E0B"},
                ],
            },
            "data": data,
        }

    except Exception as e:
        logger.warning(f"Competitor overview query error: {e}")
        return {
            "chart_type": "bar",
            "title": "Đối thủ cạnh tranh (TinyFish Market Intel)",
            "description": "Lỗi khi truy vấn dữ liệu đối thủ",
            "config": {
                "xAxis": {"dataKey": "product_name", "label": "Sản phẩm"},
                "series": [{"dataKey": "price", "name": "Giá bán", "color": "#EF4444"}],
            },
            "data": [],
        }
