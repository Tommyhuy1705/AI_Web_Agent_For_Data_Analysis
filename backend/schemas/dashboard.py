"""Pydantic schemas for Dashboard endpoints."""
from typing import Any, Optional
from pydantic import BaseModel


class KPISummary(BaseModel):
    total_revenue: float
    total_orders: int
    total_customers: int
    avg_order_value: float


class DashboardData(BaseModel):
    revenue_summary: KPISummary
    monthly_revenue: list[dict[str, Any]]
    top_products: list[dict[str, Any]]
    customer_segments: list[dict[str, Any]]
    daily_revenue: list[dict[str, Any]]
    channel_distribution: list[dict[str, Any]]


class ChartData(BaseModel):
    chart_type: str
    title: str
    data: list[dict[str, Any]]
    config: Optional[dict[str, Any]] = None
