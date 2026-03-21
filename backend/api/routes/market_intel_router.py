"""
Market Intelligence API Router
Endpoints cho TinyFish market data crawling và querying.

Endpoints:
- POST /api/market-intel/crawl       - Trigger manual crawl
- GET  /api/market-intel/summary     - Get market intel summary
- GET  /api/market-intel/competitors - Get competitor prices
- GET  /api/market-intel/status      - Check TinyFish config status
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.services.tinyfish_service import (
    is_configured,
    run_competitor_crawl,
    get_market_intel_summary,
    get_competitor_context_for_alarm,
)
from backend.services.db_executor import execute_safe_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/market-intel", tags=["Market Intelligence"])


# ============================================================
# Request/Response Models
# ============================================================

class CrawlRequest(BaseModel):
    keywords: Optional[List[str]] = None
    sources: Optional[List[str]] = ["shopee"]


class CrawlResponse(BaseModel):
    status: str
    message: str
    data: dict = {}


# ============================================================
# Endpoints
# ============================================================

@router.get("/status")
async def market_intel_status():
    """Check TinyFish configuration status."""
    configured = is_configured()
    summary = await get_market_intel_summary() if configured else {}

    return {
        "tinyfish_configured": configured,
        "has_market_data": summary.get("has_data", False),
        "total_records": summary.get("total_records", 0),
        "latest_crawl": summary.get("latest_crawl"),
        "message": (
            "TinyFish is configured and ready"
            if configured
            else "TinyFish API key not configured. Set TINYFISH_API_KEY in .env"
        ),
    }


@router.post("/crawl")
async def trigger_crawl(request: CrawlRequest):
    """
    Trigger manual market intelligence crawl.
    Cào giá đối thủ trên Shopee/Tiki cho các keywords chỉ định.
    """
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="TinyFish API key not configured. Set TINYFISH_API_KEY in .env",
        )

    logger.info(
        f"Manual crawl triggered: keywords={request.keywords}, sources={request.sources}"
    )

    try:
        report = await run_competitor_crawl(
            keywords=request.keywords,
            sources=request.sources,
        )
        return CrawlResponse(
            status=report.get("status", "completed"),
            message=(
                f"Crawl completed: {report.get('total_products_found', 0)} products found, "
                f"{report.get('total_products_saved', 0)} saved"
            ),
            data=report,
        )
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def market_intel_summary_endpoint():
    """Get market intelligence data summary."""
    try:
        summary = await get_market_intel_summary()
        return summary
    except Exception as e:
        logger.error(f"Summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competitors")
async def get_competitors(
    keyword: Optional[str] = Query(None, description="Filter by keyword"),
    source: Optional[str] = Query(None, description="Filter by source (shopee, tiki)"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get competitor prices data.
    Trả về danh sách giá đối thủ đã cào được.
    """
    try:
        # Build query
        conditions = []
        if keyword:
            conditions.append(f"keyword = '{keyword}'")
        if source:
            conditions.append(f"source = '{source}'")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = (
            f"SELECT id, source, product_name, price, original_price, "
            f"discount_pct, sold_count, rating, seller_name, keyword, crawled_at "
            f"FROM competitor_prices "
            f"WHERE {where_clause} "
            f"ORDER BY crawled_at DESC "
            f"LIMIT {limit}"
        )

        results = await execute_safe_query(query)
        return {
            "total": len(results),
            "data": results,
        }
    except Exception as e:
        logger.error(f"Competitors query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/competitor-context")
async def get_competitor_alarm_context():
    """
    Get competitor context for alarm enrichment.
    Trả về text mô tả tình hình đối thủ gần nhất.
    """
    try:
        context = await get_competitor_context_for_alarm()
        return {
            "has_context": context is not None,
            "context": context or "Chưa có dữ liệu đối thủ. Hãy chạy crawl trước.",
        }
    except Exception as e:
        logger.error(f"Competitor context error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
