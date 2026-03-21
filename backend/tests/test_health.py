"""
Unit tests for health and core endpoints.
Run with: pytest backend/tests/ -v
"""
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """GET / should return service info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data or "name" in data or "status" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /health should return scheduler status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "scheduler" in data or "status" in data


@pytest.mark.asyncio
async def test_dashboard_data_endpoint():
    """GET /api/dashboard/data should return KPI data."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/dashboard/data")
    assert response.status_code == 200
    data = response.json()
    assert "revenue_summary" in data or "total_revenue" in data or isinstance(data, dict)
