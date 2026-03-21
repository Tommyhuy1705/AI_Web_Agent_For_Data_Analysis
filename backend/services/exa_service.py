"""
Exa Market Intelligence Service
Sử dụng Exa Neural Search để tìm kiếm tin tức định tính:
- Lý do biến động doanh thu (Why)
- Xu hướng thị trường (Market Trends)
- Tin tức đối thủ cạnh tranh
- Bối cảnh vĩ mô (thời tiết, sự kiện, chính sách)

Tool: market_qual_search
Kích hoạt khi: người dùng hỏi TẠI SAO có biến động, cần tin tức, bối cảnh,
               xu hướng thị trường, lý do vĩ mô.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXA_API_KEY = os.getenv("EXA_API_KEY", "")


def is_configured() -> bool:
    """Check if Exa API key is configured."""
    return bool(EXA_API_KEY)


async def search_market_news(
    query: str,
    num_results: int = 3,
    days_back: int = 30,
    include_domains: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Tìm kiếm tin tức thị trường định tính qua Exa Neural Search.

    Args:
        query: Câu hỏi hoặc từ khóa tìm kiếm (ví dụ: "tại sao doanh thu giảm tháng 3")
        num_results: Số bài báo trả về (mặc định 3)
        days_back: Tìm trong bao nhiêu ngày gần đây (mặc định 30 ngày)
        include_domains: Giới hạn tìm trong các domain cụ thể

    Returns:
        Danh sách bài báo với title, url, summary, published_date
    """
    if not is_configured():
        logger.warning("Exa API key not configured — EXA_API_KEY is missing")
        return []

    try:
        from exa_py import Exa

        exa = Exa(api_key=EXA_API_KEY)

        # Tính khoảng thời gian tìm kiếm
        start_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        search_kwargs: Dict[str, Any] = {
            "query": query,
            "num_results": num_results,
            "start_published_date": start_date,
            "use_autoprompt": True,
            "type": "neural",
        }

        if include_domains:
            search_kwargs["include_domains"] = include_domains

        # Gọi Exa search với text contents để lấy tóm tắt
        result = exa.search_and_contents(
            **search_kwargs,
            text={"max_characters": 1000},
            highlights={"num_sentences": 3, "highlights_per_url": 1},
        )

        articles = []
        for item in result.results:
            article = {
                "title": getattr(item, "title", ""),
                "url": getattr(item, "url", ""),
                "published_date": getattr(item, "published_date", ""),
                "author": getattr(item, "author", ""),
                "summary": "",
                "highlights": [],
            }

            # Lấy highlights (tóm tắt ngắn)
            if hasattr(item, "highlights") and item.highlights:
                article["highlights"] = item.highlights
                article["summary"] = " ".join(item.highlights[:2])
            elif hasattr(item, "text") and item.text:
                article["summary"] = item.text[:500]

            articles.append(article)

        logger.info(
            f"Exa search completed: query='{query[:60]}', found={len(articles)} articles"
        )
        return articles

    except ImportError:
        logger.error("exa-py not installed. Run: pip install exa-py")
        return []
    except Exception as e:
        logger.error(f"Exa search error: {e}")
        return []


async def get_market_context(
    topic: str,
    context_type: str = "general",
) -> Dict[str, Any]:
    """
    Lấy bối cảnh thị trường cho một chủ đề cụ thể.

    Args:
        topic: Chủ đề cần tìm (ví dụ: "iPhone sales Vietnam", "retail revenue drop")
        context_type: Loại bối cảnh: "competitor", "trend", "macro", "weather", "general"

    Returns:
        Dict với articles list và synthesized_context string
    """
    # Tùy chỉnh query theo loại bối cảnh
    query_templates = {
        "competitor": f"competitor news analysis {topic} market share pricing strategy",
        "trend": f"market trend {topic} consumer behavior demand forecast",
        "macro": f"macroeconomic impact {topic} Vietnam economy policy",
        "weather": f"weather impact {topic} retail sales seasonal",
        "general": f"why {topic} market analysis business insight",
    }

    query = query_templates.get(context_type, query_templates["general"])

    articles = await search_market_news(query=query, num_results=3, days_back=60)

    if not articles:
        return {
            "topic": topic,
            "context_type": context_type,
            "articles": [],
            "synthesized_context": f"Không tìm được tin tức liên quan đến '{topic}'. Vui lòng kiểm tra lại EXA_API_KEY.",
            "source_count": 0,
        }

    # Tổng hợp context từ các bài báo
    context_parts = []
    for i, article in enumerate(articles, 1):
        if article.get("summary"):
            context_parts.append(
                f"[{i}] {article['title']}: {article['summary']}"
            )

    synthesized = (
        f"Tìm thấy {len(articles)} nguồn tin liên quan đến '{topic}':\n"
        + "\n".join(context_parts)
    )

    return {
        "topic": topic,
        "context_type": context_type,
        "articles": articles,
        "synthesized_context": synthesized,
        "source_count": len(articles),
    }


async def analyze_revenue_drop_context(
    product_category: Optional[str] = None,
    region: Optional[str] = None,
    drop_percentage: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Phân tích bối cảnh khi phát hiện doanh thu giảm.
    Được gọi tự động trong Hybrid mode khi alarm phát hiện revenue drop.

    Args:
        product_category: Danh mục sản phẩm bị ảnh hưởng
        region: Khu vực địa lý
        drop_percentage: Phần trăm giảm (ví dụ: -15.5)

    Returns:
        Bối cảnh tổng hợp từ tin tức + xu hướng
    """
    # Xây dựng query dựa trên thông tin có sẵn
    query_parts = ["Vietnam retail sales decline"]
    if product_category:
        query_parts.append(product_category)
    if region:
        query_parts.append(region)
    if drop_percentage and drop_percentage < -10:
        query_parts.append("significant revenue drop cause")

    query = " ".join(query_parts)

    articles = await search_market_news(
        query=query,
        num_results=3,
        days_back=14,  # Chỉ tìm trong 2 tuần gần nhất
    )

    context_summary = ""
    if articles:
        summaries = [a["summary"] for a in articles if a.get("summary")]
        context_summary = " | ".join(summaries[:3])
    else:
        context_summary = "Không tìm được bối cảnh tin tức liên quan."

    return {
        "query_used": query,
        "articles": articles,
        "context_summary": context_summary,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
    }
