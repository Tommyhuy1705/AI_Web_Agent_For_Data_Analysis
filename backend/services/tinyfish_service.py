"""
TinyFish Market Intelligence Service
Sử dụng TinyFish (AgentQL) API để cào dữ liệu thị trường:
- Giá đối thủ trên Shopee, Tiki
- Review sản phẩm
- Giá nguyên vật liệu trên Alibaba

Flow:
1. Gọi TinyFish API (sync hoặc SSE) với URL + goal
2. Parse kết quả JSON trả về
3. Lưu raw_data vào raw_market_intel
4. Transform thành competitor_prices (nếu là crawl_type = competitor_price)
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "")
TINYFISH_BASE_URL = "https://agent.tinyfish.ai/v1/automation"

# ============================================================
# Data Limits Configuration
# ============================================================
# Crawl modes: quick (speed-optimized) vs full (comprehensive)
CRAWL_MODE = os.getenv("TINYFISH_CRAWL_MODE", "quick")  # "quick" or "full"

# QUICK MODE: Fast crawl for UI response
QUICK_MODE_CONFIG = {
    "max_keywords": 2,           # Crawl only 2 keywords
    "max_products_per_keyword": 5,  # 5 products per keyword
    "sources": ["shopee"],       # Only Shopee for speed
    "timeout": 60,               # Fail fast at 60s
    "max_total_items": 10,       # Hard limit: 10 items total
}

# FULL MODE: Comprehensive crawl for background jobs
FULL_MODE_CONFIG = {
    "max_keywords": 3,           # Crawl 3 keywords
    "max_products_per_keyword": 10,  # 10 products per keyword
    "sources": ["shopee", "tiki"],   # Shopee + Tiki
    "timeout": 120,              # Standard timeout
    "max_total_items": 60,       # Hard limit: 60 items total
}

CRAWL_CONFIG = QUICK_MODE_CONFIG if CRAWL_MODE == "quick" else FULL_MODE_CONFIG

# Default crawl targets - Sản phẩm của doanh nghiệp bán
DEFAULT_KEYWORDS = [
    "iPhone 15 Pro Max",
    "Samsung Galaxy S24 Ultra",
    "MacBook Air M3",
    "Tai nghe Sony WH-1000XM5",
    "Nike Air Max 90",
    "Áo khoác Uniqlo",
]

# Shopee search URL template
SHOPEE_SEARCH_URL = "https://shopee.vn/search?keyword={keyword}"
TIKI_SEARCH_URL = "https://tiki.vn/search?q={keyword}"


def is_configured() -> bool:
    """Check if TinyFish API key is configured."""
    return bool(TINYFISH_API_KEY)


def _get_headers() -> dict:
    """Get headers for TinyFish API."""
    return {
        "Content-Type": "application/json",
        "X-API-Key": TINYFISH_API_KEY,
    }


# ============================================================
# Core TinyFish API Calls
# ============================================================

async def crawl_url_sync(
    url: str,
    goal: str,
    browser_profile: str = "stealth",
    timeout: int = 120,
) -> Optional[Dict[str, Any]]:
    """
    Gọi TinyFish synchronous API để cào dữ liệu từ một URL.
    Returns kết quả JSON hoặc None nếu thất bại.
    """
    if not is_configured():
        logger.warning("TinyFish API key not configured")
        return None

    payload = {
        "url": url,
        "goal": goal,
        "browser_profile": browser_profile,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{TINYFISH_BASE_URL}/run",
                json=payload,
                headers=_get_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "COMPLETED":
                    logger.info(
                        f"TinyFish crawl completed: {url} "
                        f"(steps: {result.get('num_of_steps', 'N/A')})"
                    )
                    return result.get("result")
                else:
                    error = result.get("error", {})
                    logger.warning(
                        f"TinyFish crawl failed: {error.get('message', 'Unknown error')}"
                    )
                    return None
            else:
                logger.error(
                    f"TinyFish API error {response.status_code}: {response.text[:200]}"
                )
                return None

    except httpx.TimeoutException:
        logger.error(f"TinyFish crawl timeout for URL: {url}")
        return None
    except Exception as e:
        logger.error(f"TinyFish crawl error: {e}")
        return None


async def crawl_url_sse(
    url: str,
    goal: str,
    browser_profile: str = "stealth",
    timeout: int = 180,
) -> Optional[Dict[str, Any]]:
    """
    Gọi TinyFish SSE API để cào dữ liệu (hỗ trợ streaming progress).
    Returns kết quả JSON hoặc None nếu thất bại.
    """
    if not is_configured():
        logger.warning("TinyFish API key not configured")
        return None

    payload = {
        "url": url,
        "goal": goal,
        "browser_profile": browser_profile,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{TINYFISH_BASE_URL}/run-sse",
                json=payload,
                headers=_get_headers(),
            ) as response:
                result_data = None
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                        event_type = event.get("type", "")

                        if event_type == "PROGRESS":
                            logger.info(
                                f"TinyFish progress: {event.get('purpose', '')}"
                            )
                        elif event_type == "COMPLETE":
                            if event.get("status") == "COMPLETED":
                                result_data = event.get("result")
                                logger.info(f"TinyFish SSE crawl completed: {url}")
                            else:
                                logger.warning(
                                    f"TinyFish SSE crawl failed: {event}"
                                )
                    except json.JSONDecodeError:
                        continue

                return result_data

    except Exception as e:
        logger.error(f"TinyFish SSE crawl error: {e}")
        return None


# ============================================================
# Crawl Strategies - Competitor Prices
# ============================================================

async def crawl_shopee_competitors(
    keyword: str,
    max_products: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Cào giá đối thủ trên Shopee cho một từ khóa.
    Returns structured JSON với danh sách sản phẩm.
    """
    url = SHOPEE_SEARCH_URL.format(keyword=keyword.replace(" ", "+"))
    goal = (
        f"Search for '{keyword}' products on this page. "
        f"Extract the top {max_products} products with these details for each: "
        f"product_name, price (in VND as number), original_price (if discounted), "
        f"discount_percentage, number_of_items_sold, rating (out of 5), "
        f"seller_name, and product_url. "
        f"Return as a JSON object with a 'products' array."
    )

    result = await crawl_url_sync(url, goal, browser_profile="stealth")
    return result


async def crawl_tiki_competitors(
    keyword: str,
    max_products: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Cào giá đối thủ trên Tiki cho một từ khóa.
    """
    url = TIKI_SEARCH_URL.format(keyword=keyword.replace(" ", "+"))
    goal = (
        f"Search for '{keyword}' products on this page. "
        f"Extract the top {max_products} products with these details for each: "
        f"product_name, price (in VND as number), original_price (if discounted), "
        f"discount_percentage, number_of_items_sold, rating (out of 5), "
        f"seller_name, and product_url. "
        f"Return as a JSON object with a 'products' array."
    )

    result = await crawl_url_sync(url, goal, browser_profile="stealth")
    return result


# ============================================================
# Crawl Strategies - Product Reviews
# ============================================================

async def crawl_product_reviews(
    product_url: str,
    source: str = "shopee",
    max_reviews: int = 20,
) -> Optional[Dict[str, Any]]:
    """
    Cào reviews của một sản phẩm cụ thể.
    Tập trung vào reviews 1-2 sao để phân tích nguyên nhân.
    """
    goal = (
        f"Go to the reviews/ratings section of this product page. "
        f"Filter for 1-star and 2-star reviews if possible. "
        f"Extract up to {max_reviews} reviews with: "
        f"reviewer_name, rating (1-5), review_text, review_date. "
        f"Return as a JSON object with a 'reviews' array."
    )

    result = await crawl_url_sync(product_url, goal, browser_profile="stealth")
    return result


# ============================================================
# Crawl Strategies - Material Costs (B2B)
# ============================================================

async def crawl_alibaba_material_prices(
    material_keyword: str,
    max_items: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Cào giá nguyên vật liệu trên Alibaba.
    """
    url = f"https://www.alibaba.com/trade/search?SearchText={material_keyword.replace(' ', '+')}"
    goal = (
        f"Search for '{material_keyword}' on this page. "
        f"Extract the top {max_items} supplier listings with: "
        f"product_name, price_range (min and max in USD), "
        f"minimum_order_quantity, supplier_name, supplier_country. "
        f"Return as a JSON object with a 'materials' array."
    )

    result = await crawl_url_sync(url, goal, browser_profile="stealth")
    return result


# ============================================================
# Data Persistence - Save to Supabase
# ============================================================

async def save_market_intel(
    source: str,
    crawl_type: str,
    keyword: str,
    raw_data: Dict[str, Any],
) -> Optional[dict]:
    """
    Lưu dữ liệu market intelligence vào raw_market_intel.
    """
    from backend.services.db_executor import insert_via_rest

    try:
        result = await insert_via_rest(
            table="raw_market_intel",
            data={
                "source": source,
                "crawl_type": crawl_type,
                "keyword": keyword,
                "raw_data": json.dumps(raw_data, ensure_ascii=False),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "processed": False,
            },
            schema="public",
        )
        logger.info(f"Saved market intel: source={source}, type={crawl_type}, keyword={keyword}")
        return result
    except Exception as e:
        logger.error(f"Failed to save market intel: {e}")
        return None


async def save_competitor_prices(
    products: List[Dict[str, Any]],
    source: str,
    keyword: str,
) -> int:
    """
    Transform và lưu competitor prices từ raw crawl data.
    Returns số lượng records đã lưu.
    """
    from backend.services.db_executor import insert_via_rest

    saved = 0
    for product in products:
        try:
            price = product.get("price")
            if isinstance(price, str):
                # Clean price string: "1.234.000₫" -> 1234000
                price = price.replace(".", "").replace(",", "").replace("₫", "").replace("đ", "").strip()
                try:
                    price = float(price)
                except ValueError:
                    price = None

            original_price = product.get("original_price")
            if isinstance(original_price, str):
                original_price = original_price.replace(".", "").replace(",", "").replace("₫", "").replace("đ", "").strip()
                try:
                    original_price = float(original_price)
                except ValueError:
                    original_price = None

            discount_pct = product.get("discount_percentage") or product.get("discount_pct") or 0
            if isinstance(discount_pct, str):
                discount_pct = discount_pct.replace("%", "").replace("-", "").strip()
                try:
                    discount_pct = float(discount_pct)
                except ValueError:
                    discount_pct = 0

            sold_count = product.get("number_of_items_sold") or product.get("sold_count") or 0
            if isinstance(sold_count, str):
                sold_count = sold_count.replace(".", "").replace(",", "").replace("k", "000").replace("K", "000").strip()
                try:
                    sold_count = int(float(sold_count))
                except ValueError:
                    sold_count = 0

            rating = product.get("rating") or 0
            if isinstance(rating, str):
                try:
                    rating = float(rating)
                except ValueError:
                    rating = 0

            data = {
                "source": source,
                "product_name": product.get("product_name", "Unknown"),
                "price": price,
                "original_price": original_price,
                "discount_pct": discount_pct,
                "sold_count": sold_count,
                "rating": rating,
                "seller_name": product.get("seller_name", ""),
                "product_url": product.get("product_url", ""),
                "keyword": keyword,
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }

            await insert_via_rest(
                table="competitor_prices",
                data=data,
                schema="public",
            )
            saved += 1

        except Exception as e:
            logger.warning(f"Failed to save competitor price: {e}")
            continue

    logger.info(f"Saved {saved}/{len(products)} competitor prices for '{keyword}' from {source}")
    return saved


# ============================================================
# Orchestration - Full Market Intel Crawl
# ============================================================

async def run_competitor_crawl(
    keywords: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    max_products: Optional[int] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Chạy competitor crawl với configurable data limits.
    
    Args:
        keywords: List of keywords to crawl (default: from config)
        sources: List of sources [shopee, tiki] (default: from config)
        max_products: Max products per keyword (default: from config)
        timeout: Timeout per crawl in seconds (default: from config)
    
    Returns:
        Summary report with crawl results.
    
    Configuration:
        - QUICK_MODE: 2 keywords, 5 products, Shopee only, 60s timeout, 10 items max
        - FULL_MODE: 3 keywords, 10 products, Shopee+Tiki, 120s timeout, 60 items max
    """
    if not is_configured():
        return {
            "status": "error",
            "message": "TinyFish API key not configured. Set TINYFISH_API_KEY in .env",
        }

    # Load configuration based on mode
    config = CRAWL_CONFIG
    keywords = keywords or DEFAULT_KEYWORDS[:config["max_keywords"]]
    sources = sources or config["sources"]
    max_products = max_products or config["max_products_per_keyword"]
    timeout = timeout or config["timeout"]
    
    logger.info(
        f"TinyFish crawl starting: mode={CRAWL_MODE}, "
        f"keywords={len(keywords)}, sources={sources}, "
        f"max_products={max_products}, timeout={timeout}s"
    )

    report = {
        "status": "completed",
        "crawl_mode": CRAWL_MODE,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "keywords": keywords,
        "sources": sources,
        "max_products_per_keyword": max_products,
        "timeout_seconds": timeout,
        "results": [],
        "total_products_found": 0,
        "total_products_saved": 0,
    }

    total_items = 0
    max_total_items = config.get("max_total_items", 60)

    for keyword in keywords:
        # Hard limit: stop if we've already processed max items
        if total_items >= max_total_items:
            logger.info(f"Hard limit reached ({total_items}/{max_total_items}). Stopping crawl.")
            break

        for source in sources:
            # Check limit again
            if total_items >= max_total_items:
                logger.info(f"Hard limit reached. Skipping {source}/{keyword}")
                break

            logger.info(f"Crawling {source} for '{keyword}' (limit: {max_products} products)...")

            try:
                # Crawl based on source
                if source == "shopee":
                    raw_result = await crawl_shopee_competitors(keyword, max_products=max_products)
                elif source == "tiki":
                    raw_result = await crawl_tiki_competitors(keyword, max_products=max_products)
                else:
                    logger.warning(f"Unknown source: {source}")
                    continue

                if raw_result is None:
                    report["results"].append({
                        "keyword": keyword,
                        "source": source,
                        "status": "failed",
                        "products_found": 0,
                        "products_saved": 0,
                    })
                    continue

                # Save raw data
                await save_market_intel(
                    source=source,
                    crawl_type="competitor_price",
                    keyword=keyword,
                    raw_data=raw_result,
                )

                # Extract and save structured competitor prices
                products = raw_result.get("products", [])
                if not products and isinstance(raw_result, list):
                    products = raw_result

                # Enforce per-source limit
                products = products[:max_products]
                
                saved_count = 0
                if products:
                    saved_count = await save_competitor_prices(
                        products=products,
                        source=source,
                        keyword=keyword,
                    )

                report["results"].append({
                    "keyword": keyword,
                    "source": source,
                    "status": "success",
                    "products_found": len(products),
                    "products_saved": saved_count,
                })
                report["total_products_found"] += len(products)
                report["total_products_saved"] += saved_count
                total_items += len(products)

                # Check if we've hit hard limit
                if total_items >= max_total_items:
                    logger.info(f"Hard limit approaching ({total_items}/{max_total_items})")

            except Exception as e:
                logger.error(f"Crawl error for {source}/{keyword}: {e}")
                report["results"].append({
                    "keyword": keyword,
                    "source": source,
                    "status": "error",
                    "error": str(e),
                })

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(
        f"Competitor crawl complete (mode: {CRAWL_MODE}): "
        f"{report['total_products_found']} found, "
        f"{report['total_products_saved']} saved (limit: {max_total_items})"
    )
    return report


async def get_market_intel_summary() -> Dict[str, Any]:
    """
    Lấy summary dữ liệu market intelligence hiện có.
    Dùng cho dashboard và alarm enrichment.
    """
    from backend.services.db_executor import execute_safe_query

    summary = {
        "has_data": False,
        "total_records": 0,
        "sources": [],
        "latest_crawl": None,
        "competitor_insights": [],
    }

    try:
        # Count total records
        count_result = await execute_safe_query(
            "SELECT COUNT(*) as cnt FROM raw_market_intel"
        )
        if count_result:
            summary["total_records"] = count_result[0].get("cnt", 0)
            summary["has_data"] = summary["total_records"] > 0

        # Get competitor price summary
        price_summary = await execute_safe_query(
            "SELECT source, keyword, COUNT(*) as total_products, "
            "AVG(price) as avg_price, MIN(price) as min_price, MAX(price) as max_price, "
            "AVG(discount_pct) as avg_discount "
            "FROM competitor_prices "
            "GROUP BY source, keyword "
            "ORDER BY MAX(crawled_at) DESC "
            "LIMIT 20"
        )
        if price_summary:
            summary["competitor_insights"] = price_summary

        # Get latest crawl time
        latest = await execute_safe_query(
            "SELECT MAX(crawled_at) as latest FROM raw_market_intel"
        )
        if latest and latest[0].get("latest"):
            summary["latest_crawl"] = latest[0]["latest"]

    except Exception as e:
        logger.warning(f"Error getting market intel summary: {e}")

    return summary


async def get_competitor_context_for_alarm(
    product_keywords: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Lấy context từ competitor data để enrichment cho alarm message.
    Trả về text mô tả tình hình đối thủ.
    """
    from backend.services.db_executor import execute_safe_query

    try:
        # Get recent competitor price changes
        recent_data = await execute_safe_query(
            "SELECT source, keyword, product_name, price, discount_pct, sold_count "
            "FROM competitor_prices "
            "WHERE crawled_at >= NOW() - INTERVAL '24 hours' "
            "ORDER BY discount_pct DESC "
            "LIMIT 10"
        )

        if not recent_data:
            return None

        # Build context string
        lines = ["📊 Tình hình đối thủ cạnh tranh (24h gần nhất):"]
        for item in recent_data:
            discount = item.get("discount_pct", 0)
            if discount and float(discount) > 0:
                lines.append(
                    f"  - {item['product_name']} ({item['source']}): "
                    f"Giá {item.get('price', 'N/A'):,.0f}đ, "
                    f"Giảm {discount}%, "
                    f"Đã bán {item.get('sold_count', 0)}"
                )

        if len(lines) > 1:
            return "\n".join(lines)
        return None

    except Exception as e:
        logger.warning(f"Error getting competitor context: {e}")
        return None
