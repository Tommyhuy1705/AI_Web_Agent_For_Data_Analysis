"""
TinyFish Market Intelligence Crawler
Standalone script để cào dữ liệu thị trường bằng TinyFish API.

Có thể chạy:
1. Standalone: python -m data_pipeline.crawler_scripts.tinyfish_market_crawler
2. Từ APScheduler trong backend (scheduled job)
3. Manual trigger qua API endpoint

Hỗ trợ 3 loại crawl:
- competitor_price: Giá đối thủ trên Shopee/Tiki
- review: Reviews sản phẩm (1-2 sao)
- material_cost: Giá nguyên vật liệu trên Alibaba
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# Load .env
from dotenv import load_dotenv

_root = Path(__file__).parent.parent.parent
load_dotenv(_root / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "")
TINYFISH_BASE_URL = "https://agent.tinyfish.ai/v1/automation"

# Supabase config for direct insertion
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

# Crawl targets
COMPETITOR_KEYWORDS = [
    "iPhone 15 Pro Max",
    "Samsung Galaxy S24 Ultra",
    "MacBook Air M3",
    "Tai nghe Sony WH-1000XM5",
    "Nike Air Max 90",
    "Áo khoác Uniqlo",
    "Dyson V15",
    "Philips Air Fryer",
    "iPad Pro M4",
]

MATERIAL_KEYWORDS = [
    "cotton fabric wholesale",
    "zipper wholesale",
    "packaging box wholesale",
]


def _get_tinyfish_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "X-API-Key": TINYFISH_API_KEY,
    }


def _get_supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ============================================================
# TinyFish API Calls
# ============================================================

async def crawl_sync(url: str, goal: str, timeout: int = 120) -> Optional[Dict]:
    """Call TinyFish synchronous API."""
    if not TINYFISH_API_KEY:
        logger.error("TINYFISH_API_KEY not set!")
        return None

    payload = {
        "url": url,
        "goal": goal,
        "browser_profile": "stealth",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"  → Calling TinyFish API for: {url[:80]}...")
            response = await client.post(
                f"{TINYFISH_BASE_URL}/run",
                json=payload,
                headers=_get_tinyfish_headers(),
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "COMPLETED":
                    logger.info(f"  ✓ Crawl completed (steps: {result.get('num_of_steps', '?')})")
                    return result.get("result")
                else:
                    error = result.get("error", {})
                    logger.warning(f"  ✗ Crawl failed: {error.get('message', 'Unknown')}")
            else:
                logger.error(f"  ✗ API error {response.status_code}: {response.text[:200]}")

    except httpx.TimeoutException:
        logger.error(f"  ✗ Timeout for: {url[:80]}")
    except Exception as e:
        logger.error(f"  ✗ Error: {e}")

    return None


# ============================================================
# Supabase Data Insertion
# ============================================================

async def insert_to_supabase(table: str, data: dict) -> bool:
    """Insert data to Supabase via REST API."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase credentials not configured!")
        return False

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                json=data,
                headers=_get_supabase_headers(),
            )
            if response.status_code in (200, 201):
                return True
            else:
                logger.error(f"Supabase insert error {response.status_code}: {response.text[:200]}")
                return False
    except Exception as e:
        logger.error(f"Supabase insert error: {e}")
        return False


# ============================================================
# Crawl Strategies
# ============================================================

async def crawl_shopee_keyword(keyword: str, max_products: int = 10) -> Dict[str, Any]:
    """Cào giá đối thủ trên Shopee cho một keyword."""
    url = f"https://shopee.vn/search?keyword={keyword.replace(' ', '+')}"
    goal = (
        f"Extract the top {max_products} product listings from this search results page. "
        f"For each product, extract: product_name, price (number in VND), "
        f"original_price (if discounted, number in VND), discount_percentage (number), "
        f"number_of_items_sold (number), rating (number out of 5), seller_name, product_url. "
        f"Return as JSON with a 'products' array."
    )

    result = await crawl_sync(url, goal)
    return {
        "keyword": keyword,
        "source": "shopee",
        "raw_result": result,
        "products": _extract_products(result) if result else [],
    }


async def crawl_tiki_keyword(keyword: str, max_products: int = 10) -> Dict[str, Any]:
    """Cào giá đối thủ trên Tiki cho một keyword."""
    url = f"https://tiki.vn/search?q={keyword.replace(' ', '+')}"
    goal = (
        f"Extract the top {max_products} product listings from this search results page. "
        f"For each product, extract: product_name, price (number in VND), "
        f"original_price (if discounted, number in VND), discount_percentage (number), "
        f"number_of_items_sold (number), rating (number out of 5), seller_name, product_url. "
        f"Return as JSON with a 'products' array."
    )

    result = await crawl_sync(url, goal)
    return {
        "keyword": keyword,
        "source": "tiki",
        "raw_result": result,
        "products": _extract_products(result) if result else [],
    }


def _extract_products(result: Any) -> List[Dict]:
    """Extract products list from various result formats."""
    if isinstance(result, dict):
        return result.get("products", [])
    elif isinstance(result, list):
        return result
    return []


def _clean_price(value: Any) -> Optional[float]:
    """Clean and parse price value."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(".", "").replace(",", "").replace("₫", "").replace("đ", "").replace("VND", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _clean_number(value: Any, default: int = 0) -> int:
    """Clean and parse number value."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.replace(".", "").replace(",", "").replace("k", "000").replace("K", "000").replace("+", "").strip()
        try:
            return int(float(cleaned))
        except ValueError:
            return default
    return default


# ============================================================
# Save Results
# ============================================================

async def save_crawl_results(crawl_result: Dict[str, Any]) -> Dict[str, int]:
    """Save crawl results to Supabase."""
    stats = {"raw_saved": 0, "prices_saved": 0}

    keyword = crawl_result["keyword"]
    source = crawl_result["source"]
    raw_result = crawl_result.get("raw_result")
    products = crawl_result.get("products", [])

    # 1. Save raw data to raw_market_intel
    if raw_result:
        success = await insert_to_supabase("raw_market_intel", {
            "source": source,
            "crawl_type": "competitor_price",
            "keyword": keyword,
            "raw_data": json.dumps(raw_result, ensure_ascii=False) if isinstance(raw_result, (dict, list)) else str(raw_result),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
            "processed": False,
        })
        if success:
            stats["raw_saved"] = 1

    # 2. Save structured competitor prices
    for product in products:
        price = _clean_price(product.get("price"))
        if not price:
            continue

        success = await insert_to_supabase("competitor_prices", {
            "source": source,
            "product_name": str(product.get("product_name", "Unknown"))[:500],
            "price": price,
            "original_price": _clean_price(product.get("original_price")),
            "discount_pct": _clean_number(product.get("discount_percentage") or product.get("discount_pct")),
            "sold_count": _clean_number(product.get("number_of_items_sold") or product.get("sold_count")),
            "rating": float(product.get("rating", 0) or 0),
            "seller_name": str(product.get("seller_name", ""))[:255],
            "product_url": str(product.get("product_url", "")),
            "keyword": keyword,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        })
        if success:
            stats["prices_saved"] += 1

    return stats


# ============================================================
# Main Orchestration
# ============================================================

async def run_full_crawl(
    keywords: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Chạy full market intelligence crawl.
    """
    keywords = keywords or COMPETITOR_KEYWORDS[:3]
    sources = sources or ["shopee"]

    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "keywords": keywords,
        "sources": sources,
        "results": [],
        "totals": {"products_found": 0, "products_saved": 0, "raw_saved": 0},
    }

    print("=" * 60)
    print("TINYFISH MARKET INTELLIGENCE CRAWLER")
    print("=" * 60)

    for keyword in keywords:
        for source in sources:
            print(f"\n[Crawling] {source.upper()} → '{keyword}'")

            if source == "shopee":
                crawl_result = await crawl_shopee_keyword(keyword)
            elif source == "tiki":
                crawl_result = await crawl_tiki_keyword(keyword)
            else:
                print(f"  ⚠ Unknown source: {source}")
                continue

            products = crawl_result.get("products", [])
            print(f"  Found {len(products)} products")

            # Save to database
            stats = await save_crawl_results(crawl_result)
            print(f"  Saved: {stats['prices_saved']} prices, {stats['raw_saved']} raw records")

            report["results"].append({
                "keyword": keyword,
                "source": source,
                "products_found": len(products),
                **stats,
            })
            report["totals"]["products_found"] += len(products)
            report["totals"]["products_saved"] += stats["prices_saved"]
            report["totals"]["raw_saved"] += stats["raw_saved"]

    report["finished_at"] = datetime.now(timezone.utc).isoformat()

    print(f"\n{'=' * 60}")
    print(f"CRAWL COMPLETE")
    print(f"  Total products found: {report['totals']['products_found']}")
    print(f"  Total products saved: {report['totals']['products_saved']}")
    print(f"  Total raw records:    {report['totals']['raw_saved']}")
    print(f"{'=' * 60}")

    return report


# ============================================================
# CLI Entry Point
# ============================================================

async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TinyFish Market Intelligence Crawler")
    parser.add_argument(
        "--keywords", nargs="+", default=None,
        help="Keywords to crawl (default: top 3 from COMPETITOR_KEYWORDS)"
    )
    parser.add_argument(
        "--sources", nargs="+", default=["shopee"],
        choices=["shopee", "tiki"],
        help="Sources to crawl (default: shopee)"
    )
    parser.add_argument(
        "--all-keywords", action="store_true",
        help="Crawl all default keywords"
    )

    args = parser.parse_args()

    if not TINYFISH_API_KEY:
        print("ERROR: TINYFISH_API_KEY not set in environment!")
        print("Set it in .env file: TINYFISH_API_KEY=sk-tinyfish-...")
        sys.exit(1)

    keywords = COMPETITOR_KEYWORDS if args.all_keywords else args.keywords
    report = await run_full_crawl(keywords=keywords, sources=args.sources)

    # Save report
    report_path = _root / "data_pipeline" / "crawl_reports"
    report_path.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = report_path / f"crawl_report_{timestamp}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to: {report_file}")


if __name__ == "__main__":
    asyncio.run(main())
