"""
Monthly Strategy Report Service
Tự động sinh báo cáo chiến lược doanh thu hàng tháng.
Chạy vào ngày 1 mỗi tháng lúc 01:00 UTC qua APScheduler.

Flow:
1. Query dữ liệu tổng hợp tháng trước từ Supabase
2. Chạy predict_revenue để dự đoán 3 tháng tới
3. Gọi OpenAI sinh báo cáo chiến lược chi tiết
4. Lưu báo cáo vào bảng monthly_insights (Supabase REST API)
5. (Optional) Gửi email báo cáo qua SendGrid
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from backend.services.db_executor import execute_safe_query, upsert_via_rest
from backend.ml_models.time_series import predict_revenue

logger = logging.getLogger(__name__)

# OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

# SendGrid config (reuse from alarm_monitor)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@omni-revenue.com")
REPORT_RECIPIENTS = [
    e.strip()
    for e in os.getenv("REPORT_RECIPIENTS", os.getenv("ALERT_RECIPIENTS", "admin@company.com")).split(",")
]


async def generate_monthly_report():
    """
    Cron job chính: Sinh báo cáo chiến lược hàng tháng.
    Chạy vào ngày 1 mỗi tháng lúc 01:00 UTC.
    """
    logger.info("=" * 50)
    logger.info("MONTHLY REPORT: Starting monthly strategy report generation...")
    logger.info("=" * 50)

    try:
        # Step 1: Xác định tháng báo cáo (tháng trước)
        now = datetime.utcnow()
        report_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        logger.info(f"Generating report for month: {report_month}")

        # Step 2: Thu thập dữ liệu
        data = await _collect_monthly_data(report_month)

        # Step 3: Chạy dự đoán
        predictions = await _run_predictions()

        # Step 4: Sinh báo cáo chiến lược
        report_content = await _generate_report_content(data, predictions, report_month)

        # Step 5: Lưu vào database
        await _save_report(report_month, report_content, data, predictions)

        # Step 6: Gửi email (nếu có cấu hình)
        await _send_report_email(report_month, report_content)

        logger.info(f"MONTHLY REPORT COMPLETE for {report_month}")
        return {
            "status": "success",
            "month": report_month,
            "report_length": len(report_content),
        }

    except Exception as e:
        logger.error(f"Monthly report error: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def _collect_monthly_data(report_month: str) -> Dict[str, Any]:
    """Thu thập dữ liệu tổng hợp cho tháng báo cáo."""
    data = {}

    # Monthly revenue overview
    try:
        monthly = await execute_safe_query("""
            SELECT month, total_orders, total_revenue, avg_order_value
            FROM v_monthly_revenue
            ORDER BY month DESC
        """)
        data["monthly_revenue"] = monthly
    except Exception as e:
        logger.error(f"Error fetching monthly revenue: {e}")
        data["monthly_revenue"] = []

    # Top products
    try:
        products = await execute_safe_query("""
            SELECT product_name, category, total_orders, total_revenue
            FROM v_product_performance
            ORDER BY total_revenue DESC
            LIMIT 10
        """)
        data["top_products"] = products
    except Exception as e:
        logger.error(f"Error fetching top products: {e}")
        data["top_products"] = []

    # Customer segments
    try:
        segments = await execute_safe_query("""
            SELECT segment, total_customers, total_orders, total_revenue
            FROM v_customer_segment_revenue
            ORDER BY total_revenue DESC
        """)
        data["customer_segments"] = segments
    except Exception as e:
        logger.error(f"Error fetching customer segments: {e}")
        data["customer_segments"] = []

    return data


async def _run_predictions() -> Dict[str, Any]:
    """Chạy dự đoán doanh thu 3 tháng tới."""
    try:
        historical = await execute_safe_query("""
            SELECT month, total_revenue
            FROM v_monthly_revenue
            ORDER BY month ASC
        """)

        if len(historical) < 3:
            return {"predictions": [], "error": "Not enough data for prediction"}

        formatted = [
            {"date": str(row["month"]), "revenue": float(row["total_revenue"])}
            for row in historical
        ]

        result = await predict_revenue(
            historical_data=formatted,
            periods=3,
            period_type="month",
        )
        return result

    except Exception as e:
        logger.error(f"Prediction error in monthly report: {e}")
        return {"predictions": [], "error": str(e)}


async def _generate_report_content(
    data: Dict[str, Any],
    predictions: Dict[str, Any],
    report_month: str,
) -> str:
    """Sinh nội dung báo cáo chiến lược bằng OpenAI."""
    try:
        prompt = f"""Bạn là Giám đốc Phân tích Dữ liệu (Chief Data Officer) của một doanh nghiệp bán lẻ.
Hãy viết BÁO CÁO CHIẾN LƯỢC DOANH THU THÁNG {report_month} dựa trên dữ liệu sau.

## DỮ LIỆU DOANH THU THEO THÁNG
{json.dumps(data.get('monthly_revenue', [])[:6], ensure_ascii=False, default=str, indent=2)}

## TOP 10 SẢN PHẨM
{json.dumps(data.get('top_products', []), ensure_ascii=False, default=str, indent=2)}

## PHÂN KHÚC KHÁCH HÀNG
{json.dumps(data.get('customer_segments', []), ensure_ascii=False, default=str, indent=2)}

## DỰ ĐOÁN 3 THÁNG TỚI
{json.dumps(predictions.get('predictions', []), ensure_ascii=False, default=str, indent=2)}
Metrics: R² = {predictions.get('metrics', {}).get('r2_score', 'N/A')}
Trend: {predictions.get('trend', {})}

## YÊU CẦU BÁO CÁO
Viết báo cáo bằng tiếng Việt, chuyên nghiệp, gồm các phần:
1. **TỔNG QUAN THÁNG** - Tóm tắt hiệu suất doanh thu, so sánh với tháng trước
2. **PHÂN TÍCH SẢN PHẨM** - Top sản phẩm, xu hướng category
3. **PHÂN TÍCH KHÁCH HÀNG** - Phân khúc nào đóng góp nhiều nhất, cơ hội tăng trưởng
4. **DỰ BÁO & XU HƯỚNG** - Dự đoán 3 tháng tới, mức độ tin cậy
5. **ĐỀ XUẤT CHIẾN LƯỢC** - 3-5 hành động cụ thể, ưu tiên rõ ràng

Sử dụng số liệu cụ thể, không ảo giác. Format Markdown."""

        response = await openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là CDO chuyên nghiệp. Viết báo cáo chiến lược sắc bén, dựa trên dữ liệu."
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=3000,
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Report generation error: {e}")
        return f"# Báo cáo Chiến lược Tháng {report_month}\n\nKhông thể sinh báo cáo tự động. Lỗi: {str(e)}\n\nVui lòng kiểm tra cấu hình OpenAI API."


async def _save_report(
    report_month: str,
    content: str,
    data: Dict[str, Any],
    predictions: Dict[str, Any],
):
    """Lưu báo cáo vào bảng monthly_insights qua Supabase REST API."""
    try:
        report_data = {
            "report_month": report_month,
            "content": content,
            "predictions_json": json.dumps(predictions.get("predictions", []), default=str),
            "metrics_json": json.dumps(predictions.get("metrics", {}), default=str),
            "data_summary_json": json.dumps({
                "monthly_count": len(data.get("monthly_revenue", [])),
                "top_products_count": len(data.get("top_products", [])),
                "segments_count": len(data.get("customer_segments", [])),
            }),
            "created_at": datetime.utcnow().isoformat(),
        }

        await upsert_via_rest(
            table="monthly_insights",
            data=report_data,
            schema="public",
        )
        logger.info(f"Report saved to monthly_insights for {report_month}")

    except Exception as e:
        logger.warning(f"Could not save report to DB (table may not exist): {e}")
        # Non-fatal: report was still generated and can be emailed


async def _send_report_email(report_month: str, content: str):
    """Gửi báo cáo qua email (SendGrid)."""
    if not SENDGRID_API_KEY:
        logger.info("SendGrid not configured, skipping report email")
        return

    try:
        import httpx

        # Convert markdown to simple HTML
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h1 style="color: #1a56db;">📊 Báo cáo Chiến lược Doanh thu - Tháng {report_month}</h1>
            <hr>
            <div style="white-space: pre-wrap; line-height: 1.6;">
{content}
            </div>
            <hr>
            <p style="color: #666; font-size: 12px;">
                Báo cáo này được sinh tự động bởi Omni-Revenue Agent.<br>
                Thời gian: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
            </p>
        </div>
        """

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json={
                    "personalizations": [{"to": [{"email": e} for e in REPORT_RECIPIENTS]}],
                    "from": {"email": SENDGRID_FROM_EMAIL, "name": "Omni-Revenue Agent"},
                    "subject": f"📊 Báo cáo Chiến lược Doanh thu - Tháng {report_month}",
                    "content": [{"type": "text/html", "value": html_content}],
                },
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if response.status_code in (200, 202):
                logger.info(f"Monthly report email sent for {report_month}")
            else:
                logger.error(f"SendGrid error: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"Report email error: {e}")
