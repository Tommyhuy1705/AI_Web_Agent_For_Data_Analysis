"""
Time Series Prediction Service (Task 4: Predictive Analytics)
Dự đoán doanh thu chiến lược sử dụng Scikit-learn.

Flow:
1. Query dữ liệu time series (tháng/quý) từ Supabase
2. Train mô hình in-memory (Linear Regression / Polynomial)
3. Trả ra con số dự đoán
4. Kết hợp ngữ cảnh sự kiện (từ Zilliz) + LLM sinh báo cáo insight
"""

import asyncio
import logging
import os
import json
from datetime import timedelta
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, r2_score

from backend.services.llm_client import chat_completion, is_configured

logger = logging.getLogger(__name__)

# Zilliz configuration (Vector DB cho Semantic Layer)
ZILLIZ_URI = os.getenv("ZILLIZ_CLOUD_URI", "")
ZILLIZ_API_KEY = os.getenv("ZILLIZ_API_KEY", "")


class TimeSeriesPredictor:
    """
    Dự đoán time series cho doanh thu.
    Sử dụng Polynomial Regression cho trend fitting.
    """

    def __init__(self, degree: int = 2):
        self.degree = degree
        self.model = None
        self.is_fitted = False
        self.metrics: Dict[str, float] = {}

    def fit(self, dates: List[str], values: List[float]) -> Dict[str, Any]:
        """
        Train mô hình từ dữ liệu time series.
        """
        if len(dates) < 3:
            raise ValueError("Cần ít nhất 3 data points để train model")

        df = pd.DataFrame({"date": pd.to_datetime(dates), "value": values})
        df = df.sort_values("date")

        df["days"] = (df["date"] - df["date"].min()).dt.days
        X = df["days"].values.reshape(-1, 1)
        y = df["value"].values

        self.model = make_pipeline(
            PolynomialFeatures(degree=self.degree, include_bias=False),
            LinearRegression()
        )
        self.model.fit(X, y)
        self.is_fitted = True

        y_pred = self.model.predict(X)
        self.metrics = {
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2_score": float(r2_score(y, y_pred)),
            "data_points": len(dates),
            "degree": self.degree,
        }

        self._min_date = df["date"].min()
        self._max_date = df["date"].max()
        self._last_value = float(y[-1])

        logger.info(f"Model trained: R2={self.metrics['r2_score']:.4f}, MAE={self.metrics['mae']:.2f}")
        return self.metrics

    def predict(self, future_periods: int = 3, period_days: int = 30) -> List[Dict[str, Any]]:
        """
        Dự đoán cho các kỳ tương lai.
        """
        if not self.is_fitted:
            raise ValueError("Model chưa được train. Gọi fit() trước.")

        predictions = []
        max_days = (self._max_date - self._min_date).days

        for i in range(1, future_periods + 1):
            future_days = max_days + (i * period_days)
            X_future = np.array([[future_days]])
            predicted_value = float(self.model.predict(X_future)[0])

            predicted_value = max(0, predicted_value)

            future_date = self._max_date + timedelta(days=i * period_days)
            predictions.append({
                "period": future_date.strftime("%Y-%m"),
                "predicted_value": round(predicted_value, 2),
                "confidence": "medium" if self.metrics["r2_score"] > 0.7 else "low",
            })

        return predictions


def _compute_prediction_sync(
    dates: List[str],
    values: List[float],
    periods: int,
    period_type: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], float]:
    """Run CPU-bound model training/prediction synchronously (for thread pool offloading)."""
    predictor = TimeSeriesPredictor(degree=2)
    metrics = predictor.fit(dates, values)

    period_days = 30 if period_type == "month" else 90
    predictions = predictor.predict(
        future_periods=periods,
        period_days=period_days,
    )

    if len(values) >= 2:
        recent_trend = ((values[-1] - values[-2]) / values[-2]) * 100 if values[-2] != 0 else 0
    else:
        recent_trend = 0

    return metrics, predictions, recent_trend


async def predict_revenue(
    historical_data: List[Dict[str, Any]] = None,
    periods: int = 3,
    period_type: str = "month"
) -> Dict[str, Any]:
    """
    API chính: Dự đoán doanh thu từ dữ liệu lịch sử.
    Nếu không truyền historical_data, tự query từ DB.
    """
    try:
        if historical_data is None:
            from backend.services.db_executor import execute_safe_query
            raw_data = await execute_safe_query(
                "SELECT month, total_revenue FROM analytics_mart.v_monthly_revenue ORDER BY month"
            )
            historical_data = [
                {"date": str(row.get("month", "")), "revenue": row.get("total_revenue", 0)}
                for row in raw_data
            ]

        if not historical_data:
            return {"error": "No historical data available", "predictions": [], "metrics": {}}

        dates = [d["date"] if isinstance(d["date"], str) else str(d["date"]) for d in historical_data]
        values = [float(d["revenue"]) for d in historical_data]

        metrics, predictions, recent_trend = await asyncio.to_thread(
            _compute_prediction_sync,
            dates,
            values,
            periods,
            period_type,
        )

        result = {
            "predictions": [
                {"month": p["period"], "predicted_revenue": p["predicted_value"], "confidence": p["confidence"]}
                for p in predictions
            ],
            "metrics": metrics,
            "trend": {
                "direction": "up" if recent_trend > 0 else "down",
                "change_pct": round(recent_trend, 2),
                "last_value": values[-1],
            },
            "historical_summary": {
                "total_periods": len(values),
                "avg_revenue": round(sum(values) / len(values), 2),
                "max_revenue": round(max(values), 2),
                "min_revenue": round(min(values), 2),
            },
        }

        return result

    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        return {
            "error": str(e),
            "predictions": [],
            "metrics": {},
        }


async def generate_strategic_insight(
    predictions: Dict[str, Any],
    context: str = "",
) -> str:
    """
    Sinh báo cáo insight chiến lược từ dự đoán + ngữ cảnh sự kiện.
    Uses centralized LLM client (Qwen or OpenAI).
    """
    if not is_configured():
        return "Unable to generate strategic insight because no LLM is configured."

    try:
        prompt = f"""You are a senior business analyst. Based on the revenue forecast below,
write a concise strategic insight report in English (3-5 short paragraphs).

Forecast data:
{json.dumps(predictions, ensure_ascii=False, indent=2)}

Additional context:
{context or "No additional context provided."}

Requirements:
1. Analyze revenue trend direction and momentum.
2. Provide an outlook for the next periods.
3. Recommend 2-3 concrete strategic actions.
4. Avoid hallucinations and stay grounded in provided data.
5. Use professional and direct business language."""

        content = await chat_completion(
            messages=[
                {"role": "system", "content": "You are a senior strategic business analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=1000,
        )

        return content

    except Exception as e:
        logger.error(f"Insight generation error: {e}")
        return "Unable to generate strategic insight. Please verify LLM configuration."


async def search_context_from_zilliz(query: str) -> str:
    """
    Tìm kiếm ngữ cảnh sự kiện từ Zilliz Vector DB (Semantic Layer).
    """
    if not ZILLIZ_URI or not ZILLIZ_API_KEY:
        logger.info("Zilliz not configured, returning empty context")
        return ""

    try:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{ZILLIZ_URI}/v1/vector/search",
                json={
                    "collectionName": "business_events",
                    "vector": [],
                    "filter": "",
                    "limit": 5,
                    "outputFields": ["event_name", "description", "date", "impact"],
                },
                headers={
                    "Authorization": f"Bearer {ZILLIZ_API_KEY}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 200:
                results = response.json().get("data", [])
                context_parts = []
                for r in results:
                    context_parts.append(
                        f"- {r.get('event_name', '')}: {r.get('description', '')} "
                        f"(Impact: {r.get('impact', 'unknown')})"
                    )
                return "\n".join(context_parts)

    except Exception as e:
        logger.error(f"Zilliz search error: {e}")

    return ""
