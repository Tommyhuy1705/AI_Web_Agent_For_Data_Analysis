"""
Test Script: TinyFish Market Crawler
Crawl dữ liệu giá đối thủ từ Tiki.vn qua TinyFish SSE API.
Kết quả: 5 sản phẩm máy lọc nước được lưu vào competitor_prices.
"""
import asyncio
import httpx
import json
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "")
DB_URL = os.getenv("SUPABASE_DATABASE_URL", "")

async def crawl_sse(url: str, goal: str, timeout: int = 120):
    """Crawl via TinyFish SSE endpoint."""
    if not TINYFISH_API_KEY:
        raise ValueError("TINYFISH_API_KEY not set in backend/.env")
    payload = {"url": url, "goal": goal, "browser_profile": "stealth"}
    headers = {"Content-Type": "application/json", "X-API-Key": TINYFISH_API_KEY}
    result = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST", "https://agent.tinyfish.ai/v1/automation/run-sse",
            json=payload, headers=headers
        ) as resp:
            print(f"  SSE Status: {resp.status_code}")
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event_type = data.get("type", "")
                        if event_type == "PROGRESS":
                            print(f"  [PROGRESS] {data.get('purpose', '')[:70]}")
                        elif event_type in ("COMPLETE", "COMPLETED"):
                            result = data.get("result")
                            print("  [COMPLETE] Crawl finished!")
                            break
                        elif event_type == "FAILED":
                            print(f"  [FAILED] {data.get('error', {})}")
                            break
                    except Exception:
                        pass
    return result

def save_to_supabase(products: list, keyword: str, source: str):
    """Save crawled products to Supabase."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    # Save raw data
    cursor.execute("""
        INSERT INTO raw_market_intel (source, crawl_type, keyword, raw_data, crawled_at, processed)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (source, "competitor_price", keyword, json.dumps({"products": products}), now, False))
    # Save individual products
    for p in products:
        cursor.execute("""
            INSERT INTO competitor_prices (source, product_name, price, original_price, discount_pct, rating, seller_name, keyword, crawled_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (source, p.get("product_name", ""), p.get("price", 0), p.get("price", 0),
              p.get("discount_percentage", 0), p.get("rating", 0), p.get("seller_name", ""), keyword, now))
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM competitor_prices WHERE keyword=%s", (keyword,))
    count = cursor.fetchone()[0]
    print(f"  ✓ Saved {len(products)} products. Total for '{keyword}': {count}")
    cursor.close()
    conn.close()

async def main():
    keyword = "may loc nuoc"
    url = f"https://tiki.vn/search?q={keyword.replace(' ', '+')}"
    goal = (
        "Extract top 5 product listings from this search results page. "
        "For each product: product_name, price (VND number), rating (0-5). "
        "Return JSON with a 'products' array."
    )
    print(f"=== TinyFish Crawler Test ===")
    print(f"Keyword: {keyword} | Source: Tiki.vn")
    result = await crawl_sse(url, goal)
    if result and "products" in result:
        products = result["products"]
        print(f"\n✓ Crawled {len(products)} products:")
        for p in products:
            print(f"  - {p.get('product_name', '')[:50]:<50} | {p.get('price', 0):>12,.0f} VND | ★{p.get('rating', 0)}")
        save_to_supabase(products, keyword, "tiki")
    else:
        print("✗ No products found")

if __name__ == "__main__":
    asyncio.run(main())
