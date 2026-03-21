"""
Exa Market Intelligence Service
Sử dụng Exa Neural Search (semantic search) để tìm kiếm tin tức định tính:
- Lý do biến động doanh thu (Why)
- Xu hướng thị trường (Market Trends)
- Tin tức đối thủ cạnh tranh
- Bối cảnh vĩ mô (thời tiết, sự kiện, chính sách)

Tool: market_qual_search
Kích hoạt khi: người dùng hỏi TẠI SAO có biến động, cần tin tức, bối cảnh,
               xu hướng thị trường, lý do vĩ mô, hoặc câu hỏi ngoài phạm vi DB.

API: exa-py SDK — verified working with search_and_contents(query, num_results, text, highlights, type)
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


def _build_exa_client():
    """Create and return an Exa client instance."""
    from exa_py import Exa
    return Exa(api_key=EXA_API_KEY)


async def search_market_news(
    query: str,
    num_results: int = 4,
    days_back: int = 60,
    include_domains: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Tìm kiếm tin tức thị trường định tính qua Exa Neural Search.

    Args:
        query: Câu hỏi hoặc từ khóa tìm kiếm
        num_results: Số bài báo trả về (mặc định 4)
        days_back: Tìm trong bao nhiêu ngày gần đây (mặc định 60 ngày)
        include_domains: Giới hạn tìm trong các domain cụ thể

    Returns:
        Danh sách bài báo với title, url, summary, published_date
    """
    if not is_configured():
        logger.warning("Exa API key not configured — EXA_API_KEY is missing")
        return []

    try:
        import asyncio
        exa = _build_exa_client()

        start_date = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build kwargs
        kwargs: Dict[str, Any] = {
            "query": query,
            "num_results": num_results,
            "text": {"max_characters": 1200},
            "highlights": {"num_sentences": 3, "highlights_per_url": 1},
            "type": "neural",
            "start_published_date": start_date,
        }

        if include_domains:
            kwargs["include_domains"] = include_domains

        # exa-py is synchronous — run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: exa.search_and_contents(**kwargs),
        )

        articles = []
        for item in result.results:
            article: Dict[str, Any] = {
                "title": getattr(item, "title", "") or "",
                "url": getattr(item, "url", "") or "",
                "published_date": getattr(item, "published_date", "") or "",
                "author": getattr(item, "author", "") or "",
                "summary": "",
                "highlights": [],
            }

            # Prefer highlights for concise summaries
            raw_highlights = getattr(item, "highlights", None)
            if raw_highlights:
                article["highlights"] = raw_highlights
                article["summary"] = " ".join(raw_highlights[:2])
            elif getattr(item, "text", None):
                article["summary"] = item.text[:600]

            articles.append(article)

        logger.info(
            f"Exa search OK: query='{query[:70]}', found={len(articles)} articles"
        )
        return articles

    except ImportError:
        logger.error("exa-py not installed. Run: pip install exa-py")
        return []
    except Exception as e:
        logger.error(f"Exa search error: {e}", exc_info=True)
        return []


async def get_market_context(
    topic: str,
    context_type: str = "general",
) -> Dict[str, Any]:
    """
    Lấy bối cảnh thị trường cho một chủ đề cụ thể.

    Args:
        topic: Chủ đề cần tìm (ví dụ: "doanh thu bán lẻ Việt Nam", "iPhone sales")
        context_type: Loại bối cảnh: "competitor", "trend", "macro", "weather", "general"

    Returns:
        Dict với articles list và synthesized_context string
    """
    # Tùy chỉnh query theo loại bối cảnh — bilingual để tăng coverage
    query_templates = {
        "competitor": (
            f"competitor analysis {topic} Vietnam market share pricing strategy 2025"
        ),
        "trend": (
            f"market trend {topic} Vietnam consumer demand forecast 2025"
        ),
        "macro": (
            f"macroeconomic Vietnam economy impact {topic} policy interest rate 2025"
        ),
        "weather": (
            f"weather seasonal impact retail sales {topic} Vietnam"
        ),
        "general": (
            f"Vietnam business market analysis {topic} insight 2025"
        ),
    }

    query = query_templates.get(context_type, query_templates["general"])
    articles = await search_market_news(query=query, num_results=4, days_back=90)

    if not articles:
        return {
            "topic": topic,
            "context_type": context_type,
            "articles": [],
            "synthesized_context": (
                f"Không tìm được tin tức liên quan đến '{topic}'. "
                "Vui lòng kiểm tra lại EXA_API_KEY hoặc thử lại với từ khóa khác."
            ),
            "source_count": 0,
        }

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
    Được gọi tự động trong Hybrid mode khi phát hiện revenue drop.
    """
    query_parts = ["Vietnam retail sales revenue decline cause"]
    if product_category:
        query_parts.append(product_category)
    if region:
        query_parts.append(region)
    if drop_percentage and drop_percentage < -10:
        query_parts.append("significant drop reason economic")

    query = " ".join(query_parts)

    articles = await search_market_news(
        query=query,
        num_results=3,
        days_back=30,
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


async def search_outside_db(
    user_question: str,
) -> Dict[str, Any]:
    """
    Tìm kiếm thông tin thị trường khi câu hỏi KHÔNG liên quan đến dữ liệu nội bộ.
    Được gọi như fallback khi LLM phát hiện câu hỏi ngoài phạm vi DB.

    Args:
        user_question: Câu hỏi gốc của người dùng

    Returns:
        Dict với articles và formatted_answer
    """
    # Xây dựng query ngữ nghĩa từ câu hỏi người dùng
    # Thêm context Vietnam để tăng độ chính xác
    query = f"Vietnam business market {user_question}"

    articles = await search_market_news(
        query=query,
        num_results=4,
        days_back=90,
    )

    if not articles:
        return {
            "articles": [],
            "formatted_answer": (
                "Tôi không tìm được thông tin liên quan đến câu hỏi của bạn qua Exa. "
                "Câu hỏi này có thể nằm ngoài phạm vi dữ liệu nội bộ và dữ liệu thị trường hiện có."
            ),
            "source_count": 0,
        }

    # Format câu trả lời
    answer_parts = [
        f"📰 **Kết quả tìm kiếm thị trường cho: \"{user_question[:100]}\"**\n"
    ]
    for i, article in enumerate(articles, 1):
        title = article.get("title", "N/A")
        summary = article.get("summary", "")
        url = article.get("url", "")
        pub_date = article.get("published_date", "")

        answer_parts.append(
            f"**[{i}] {title}**\n"
            f"{summary[:400]}\n"
            f"🔗 {url}"
            + (f"\n📅 {pub_date[:10]}" if pub_date else "")
            + "\n"
        )

    return {
        "articles": articles,
        "formatted_answer": "\n".join(answer_parts),
        "source_count": len(articles),
    }
