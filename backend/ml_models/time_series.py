"""
Time Series Prediction Service (Task 4: Predictive Analytics)
Dự đoán doanh thu chiến lược sử dụng Scikit-learn.

Flow:
1. Query dữ liệu time series (tháng/quý) từ Supabase
2. Train mô hình in-memory (Linear Regression / Polynomial)
3. Trả ra con số dự đoán
4. Kết hợp ngữ cảnh sự kiện (từ Zilliz) + OpenAI sinh báo cáo insight
"""

import logging
import os
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, r2_score

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

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

        Args:
            dates: Danh sách ngày/tháng (format: YYYY-MM-DD hoặc YYYY-MM)
            values: Danh sách giá trị doanh thu tương ứng

        Returns:
            Dict chứa metrics của model
        """
        if len(dates) < 3:
            raise ValueError("Cần ít nhất 3 data points để train model")

        # Convert dates to numeric features
        df = pd.DataFrame({"date": pd.to_datetime(dates), "value": values})
        df = df.sort_values("date")

        # Feature: số ngày kể từ ngày đầu tiên
        df["days"] = (df["date"] - df["date"].min()).dt.days
        X = df["days"].values.reshape(-1, 1)
        y = df["value"].values

        # Train Polynomial Regression
        self.model = make_pipeline(
            PolynomialFeatures(degree=self.degree, include_bias=False),
            LinearRegression()
        )
        self.model.fit(X, y)
        self.is_fitted = True

        # Calculate metrics
        y_pred = self.model.predict(X)
        self.metrics = {
            "mae": float(mean_absolute_error(y, y_pred)),
            "r2_score": float(r2_score(y, y_pred)),
            "data_points": len(dates),
            "degree": self.degree,
        }

        # Store reference data
        self._min_date = df["date"].min()
        self._max_date = df["date"].max()
        self._last_value = float(y[-1])

        logger.info(f"Model trained: R2={self.metrics['r2_score']:.4f}, MAE={self.metrics['mae']:.2f}")
        return self.metrics

    def predict(self, future_periods: int = 3, period_days: int = 30) -> List[Dict[str, Any]]:
        """
        Dự đoán cho các kỳ tương lai.

        Args:
            future_periods: Số kỳ cần dự đoán
            period_days: Số ngày mỗi kỳ (30 = tháng, 90 = quý)

        Returns:
            List các dict chứa ngày và giá trị dự đoán
        """
        if not self.is_fitted:
            raise ValueError("Model chưa được train. Gọi fit() trước.")

        predictions = []
        max_days = (self._max_date - self._min_date).days

        for i in range(1, future_periods + 1):
            future_days = max_days + (i * period_days)
            X_future = np.array([[future_days]])
            predicted_value = float(self.model.predict(X_future)[0])

            # Đảm bảo giá trị dự đoán không âm
            predicted_value = max(0, predicted_value)

            future_date = self._max_date + timedelta(days=i * period_days)
            predictions.append({
                "period": future_date.strftime("%Y-%m"),
                "predicted_value": round(predicted_value, 2),
                "confidence": "medium" if self.metrics["r2_score"] > 0.7 else "low",
            })

        return predictions


async def predict_revenue(
    historical_data: List[Dict[str, Any]],
    periods: int = 3,
    period_type: str = "month"
) -> Dict[str, Any]:
    """
    API chính: Dự đoán doanh thu từ dữ liệu lịch sử.

    Args:
        historical_data: List dict với keys 'date' và 'revenue'
        periods: Số kỳ cần dự đoán
        period_type: 'month' hoặc 'quarter'

    Returns:
        Dict chứa predictions, metrics, và insight
    """
    try:
        dates = [d["date"] if isinstance(d["date"], str) else str(d["date"]) for d in historical_data]
        values = [float(d["revenue"]) for d in historical_data]

        # Train model
        predictor = TimeSeriesPredictor(degree=2)
        metrics = predictor.fit(dates, values)

        # Predict
        period_days = 30 if period_type == "month" else 90
        predictions = predictor.predict(
            future_periods=periods,
            period_days=period_days
        )

        # Tính trend
        if len(values) >= 2:
            recent_trend = ((values[-1] - values[-2]) / values[-2]) * 100 if values[-2] != 0 else 0
        else:
            recent_trend = 0

        result = {
            "predictions": predictions,
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
    model: str = "gpt-4.1-mini"
) -> str:
    """
    Sinh báo cáo insight chiến lược từ dự đoán + ngữ cảnh sự kiện.

    Args:
        predictions: Kết quả từ predict_revenue()
        context: Ngữ cảnh bổ sung (từ Zilliz Vector DB)
        model: OpenAI model

    Returns:
        Báo cáo insight chiến lược bằng tiếng Việt
    """
    try:
        prompt = f"""Bạn là một chuyên gia phân tích kinh doanh. Dựa trên dữ liệu dự đoán doanh thu sau,
hãy viết một báo cáo insight chiến lược ngắn gọn (3-5 đoạn) bằng tiếng Việt.

Dữ liệu dự đoán:
{json.dumps(predictions, ensure_ascii=False, indent=2)}

Ngữ cảnh bổ sung:
{context or "Không có ngữ cảnh bổ sung."}

Yêu cầu:
1. Phân tích xu hướng doanh thu
2. Đưa ra nhận định về các kỳ tới
3. Đề xuất 2-3 hành động chiến lược cụ thể
4. Không ảo giác - chỉ dựa trên dữ liệu thực
5. Sử dụng ngôn ngữ chuyên nghiệp, sắc bén"""

        response = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia phân tích kinh doanh cấp cao."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=1000,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Insight generation error: {e}")
        return "Không thể sinh báo cáo insight. Vui lòng kiểm tra cấu hình OpenAI API."


async def search_context_from_zilliz(query: str) -> str:
    """
    Tìm kiếm ngữ cảnh sự kiện từ Zilliz Vector DB (Semantic Layer).
    Ví dụ: "Sắp có chiến dịch Black Friday"

    Returns:
        Chuỗi ngữ cảnh liên quan
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
                    "vector": [],  # Sẽ được encode bởi Zilliz
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
