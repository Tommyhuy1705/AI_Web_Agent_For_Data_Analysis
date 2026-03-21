"""Pydantic schemas for Market Intelligence endpoints."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CrawlRequest(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=200)
    source: str = Field(default="tiki", pattern="^(tiki|shopee|lazada)$")
    max_products: int = Field(default=10, ge=1, le=50)


class CompetitorPrice(BaseModel):
    source: str
    product_name: str
    price: float
    original_price: Optional[float] = None
    discount_pct: Optional[float] = None
    rating: Optional[float] = None
    sold_count: Optional[int] = None
    seller_name: Optional[str] = None
    product_url: Optional[str] = None
    keyword: str
    crawled_at: datetime
