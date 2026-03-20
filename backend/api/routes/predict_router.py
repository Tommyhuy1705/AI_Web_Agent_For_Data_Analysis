"""
Predict Router - Predictive Analytics Endpoint (Task 4)
Cung cấp API cho dự đoán doanh thu và sinh insight chiến lược.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.db_executor import execute_safe_query
from backend.ml_models.time_series import (
    predict_revenue,
    generate_strategic_insight,
    search_context_from_zilliz,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predict", tags=["Predictive Analytics"])


class PredictRequest(BaseModel):
    """Request body cho prediction."""
    periods: int = Field(3, description="Số kỳ cần dự đoán", ge=1, le=12)
    period_type: str = Field("month", description="Loại kỳ: month hoặc quarter")
    include_insight: bool = Field(True, description="Có sinh insight chiến lược không")


class PredictResponse(BaseModel):
    """Response body cho prediction."""
    success: bool
    predictions: list = []
    metrics: dict = {}
    trend: dict = {}
    historical_summary: dict = {}
    insight: Optional[str] = None
    error: Optional[str] = None


@router.post("/revenue", response_model=PredictResponse)
async def predict_revenue_endpoint(request: PredictRequest):
    """
    Dự đoán doanh thu tương lai.

    Flow:
    1. Query dữ liệu time series từ analytics_mart
    2. Train mô hình in-memory
    3. Trả ra con số dự đoán
    4. (Optional) Sinh insight chiến lược
    """
    logger.info(f"Predict request: {request.periods} {request.period_type}s")

    try:
        # Step 1: Query historical data
        if request.period_type == "quarter":
            query = """
                SELECT
                    DATE_TRUNC('quarter', order_date)::DATE as date,
                    SUM(total_amount) as revenue
                FROM analytics_mart.fact_sales
                GROUP BY DATE_TRUNC('quarter', order_date)
                ORDER BY date
            """
        else:
            query = """
                SELECT
                    DATE_TRUNC('month', order_date)::DATE as date,
                    SUM(total_amount) as revenue
                FROM analytics_mart.fact_sales
                GROUP BY DATE_TRUNC('month', order_date)
                ORDER BY date
            """

        historical_data = await execute_safe_query(query)

        if len(historical_data) < 3:
            return PredictResponse(
                success=False,
                error="Cần ít nhất 3 kỳ dữ liệu lịch sử để dự đoán. Hiện có: " + str(len(historical_data)),
            )

        # Convert to serializable format
        formatted_data = [
            {"date": str(row["date"]), "revenue": float(row["revenue"])}
            for row in historical_data
        ]

        # Step 2: Predict
        result = await predict_revenue(
            historical_data=formatted_data,
            periods=request.periods,
            period_type=request.period_type,
        )

        if "error" in result and result["error"]:
            return PredictResponse(success=False, error=result["error"])

        # Step 3: Generate insight (optional)
        insight = None
        if request.include_insight:
            # Tìm ngữ cảnh từ Zilliz
            context = await search_context_from_zilliz("revenue forecast business events")
            insight = await generate_strategic_insight(result, context)

        return PredictResponse(
            success=True,
            predictions=result.get("predictions", []),
            metrics=result.get("metrics", {}),
            trend=result.get("trend", {}),
            historical_summary=result.get("historical_summary", {}),
            insight=insight,
        )

    except Exception as e:
        logger.error(f"Prediction endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def predict_health():
    """Health check cho prediction service."""
    return {
        "status": "healthy",
        "service": "predictive_analytics",
        "models": ["polynomial_regression"],
    }
