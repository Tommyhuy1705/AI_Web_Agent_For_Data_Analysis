"""
Alarm Monitor Service
Logic so sánh snapshot 1h cho tính năng Proactive Alarm.
Chạy mỗi 60 phút qua APScheduler.

Flow:
1. Query tổng doanh thu giờ vừa qua từ fact_sales (public schema)
2. So sánh với value trong hourly_snapshot
3. Nếu giảm > 15%: UPSERT value mới -> Gọi webhook Dify -> SendGrid email -> SSE thông báo
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

from backend.services.db_executor import (
    execute_safe_query,
    fetch_one,
    upsert_via_rest,
)

logger = logging.getLogger(__name__)

# Configuration
ALARM_THRESHOLD_PCT = 15.0  # Ngưỡng cảnh báo: giảm > 15%
DIFY_WEBHOOK_URL = os.getenv("DIFY_WEBHOOK_URL", "")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@omni-revenue.com")
ALERT_RECIPIENTS = [e.strip() for e in os.getenv("ALERT_RECIPIENTS", "admin@company.com").split(",")]

# SSE event queue (sẽ được inject từ main.py)
_alarm_event_queue = None


def set_alarm_event_queue(queue):
    """Set event queue cho SSE alarm notifications."""
    global _alarm_event_queue
    _alarm_event_queue = queue


async def check_hourly_revenue_alarm():
    """
    Task chính: Kiểm tra doanh thu theo giờ và phát cảnh báo nếu giảm bất thường.
    Được gọi bởi APScheduler mỗi 60 phút.
    """
    logger.info("=" * 50)
    logger.info("ALARM MONITOR: Starting hourly revenue check...")
    logger.info("=" * 50)

    try:
        # Step 1: Query tổng doanh thu giờ vừa qua
        current_revenue = await _get_current_hour_revenue()
        logger.info(f"Current hour revenue: {current_revenue}")

        if current_revenue is None:
            logger.warning("No revenue data for current hour")
            return

        # Step 2: Lấy giá trị snapshot trước đó
        previous_snapshot = await _get_previous_snapshot("hourly_revenue")
        previous_value = previous_snapshot.get("value", 0) if previous_snapshot else 0
        logger.info(f"Previous snapshot value: {previous_value}")

        # Step 3: Tính phần trăm thay đổi
        if previous_value > 0:
            change_pct = ((current_revenue - previous_value) / previous_value) * 100
        else:
            change_pct = 0

        logger.info(f"Revenue change: {change_pct:.2f}%")

        # Step 4: UPSERT giá trị mới vào hourly_snapshot
        await _upsert_snapshot("hourly_revenue", current_revenue, previous_value, change_pct)

        # Step 5: Kiểm tra ngưỡng cảnh báo
        if change_pct < -ALARM_THRESHOLD_PCT:
            logger.warning(f"ALARM TRIGGERED! Revenue dropped {abs(change_pct):.2f}%")
            await _trigger_alarm(current_revenue, previous_value, change_pct)
        else:
            logger.info("Revenue within normal range. No alarm triggered.")

    except Exception as e:
        logger.error(f"Alarm monitor error: {e}", exc_info=True)


async def _get_current_hour_revenue() -> Optional[float]:
    """Query tổng doanh thu trong ngày hôm nay từ fact_sales (public schema)."""
    try:
        result = await fetch_one("""
            SELECT COALESCE(SUM(total_amount), 0) as total_revenue
            FROM fact_sales
            WHERE order_date = CURRENT_DATE
        """)
        return float(result["total_revenue"]) if result else None
    except Exception as e:
        logger.error(f"Error querying current revenue: {e}")
        # Fallback: lấy doanh thu gần nhất
        try:
            result = await fetch_one("""
                SELECT COALESCE(SUM(total_amount), 0) as total_revenue
                FROM fact_sales
                WHERE order_date >= CURRENT_DATE - INTERVAL '7 days'
            """)
            return float(result["total_revenue"]) if result else 0
        except Exception:
            return None


async def _get_previous_snapshot(metric_name: str) -> Optional[Dict[str, Any]]:
    """Lấy giá trị snapshot trước đó từ hourly_snapshot (public schema)."""
    try:
        result = await fetch_one(f"""
            SELECT metric_name, value, previous_value, change_pct, last_updated
            FROM hourly_snapshot
            WHERE metric_name = '{metric_name}'
        """)
        return result
    except Exception as e:
        logger.error(f"Error fetching snapshot: {e}")
        return None


async def _upsert_snapshot(
    metric_name: str,
    current_value: float,
    previous_value: float,
    change_pct: float
):
    """UPSERT giá trị mới vào hourly_snapshot (public schema via REST API)."""
    try:
        await upsert_via_rest(
            table="hourly_snapshot",
            data={
                "metric_name": metric_name,
                "value": current_value,
                "previous_value": previous_value,
                "change_pct": round(change_pct, 4),
                "last_updated": datetime.utcnow().isoformat(),
            },
            schema="public",
        )
        logger.info(f"Snapshot updated: {metric_name} = {current_value}")
    except Exception as e:
        logger.error(f"Error upserting snapshot: {e}")


async def _trigger_alarm(
    current_revenue: float,
    previous_revenue: float,
    change_pct: float
):
    """
    Kích hoạt chuỗi cảnh báo:
    1. Gọi webhook Dify để sinh câu cảnh báo tự nhiên
    2. Gửi email qua SendGrid
    3. Đẩy thông báo SSE lên Frontend
    """
    alarm_data = {
        "type": "revenue_alarm",
        "severity": "critical" if change_pct < -30 else "warning",
        "current_revenue": current_revenue,
        "previous_revenue": previous_revenue,
        "change_pct": round(change_pct, 2),
        "timestamp": datetime.utcnow().isoformat(),
        "message": f"Cảnh báo: Doanh thu giảm {abs(change_pct):.1f}% so với giờ trước "
                   f"(Hiện tại: {current_revenue:,.0f} VNĐ, Trước đó: {previous_revenue:,.0f} VNĐ)"
    }

    # 1. Gọi Dify webhook (nếu có cấu hình)
    natural_message = await _call_dify_alarm_webhook(alarm_data)
    if natural_message:
        alarm_data["natural_message"] = natural_message

    # 2. Gửi email qua SendGrid (nếu có cấu hình)
    await _send_alarm_email(alarm_data)

    # 3. Đẩy SSE event
    await _push_sse_alarm(alarm_data)

    logger.info("Alarm triggered and notifications sent")


async def _call_dify_alarm_webhook(alarm_data: Dict[str, Any]) -> Optional[str]:
    """Gọi Dify webhook để sinh câu cảnh báo tự nhiên."""
    if not DIFY_WEBHOOK_URL or not DIFY_API_KEY:
        logger.info("Dify webhook not configured, skipping")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                DIFY_WEBHOOK_URL,
                json={
                    "inputs": {
                        "alarm_type": alarm_data["type"],
                        "change_pct": str(alarm_data["change_pct"]),
                        "current_value": str(alarm_data["current_revenue"]),
                        "previous_value": str(alarm_data["previous_revenue"]),
                    },
                    "response_mode": "blocking",
                    "user": "alarm_system",
                },
                headers={
                    "Authorization": f"Bearer {DIFY_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("answer", result.get("text", ""))
    except Exception as e:
        logger.error(f"Dify webhook error: {e}")
    return None


async def _send_alarm_email(alarm_data: Dict[str, Any]):
    """Gửi email cảnh báo qua SendGrid API."""
    if not SENDGRID_API_KEY:
        logger.info("SendGrid API key not configured, skipping email")
        return

    try:
        severity_emoji = "🔴" if alarm_data["severity"] == "critical" else "🟡"
        subject = f"{severity_emoji} Omni-Revenue Alert: Doanh thu giảm {abs(alarm_data['change_pct'])}%"

        html_content = f"""
        <h2>{severity_emoji} Cảnh báo Doanh thu Bất thường</h2>
        <table border="1" cellpadding="8" cellspacing="0">
            <tr><td><strong>Thời gian</strong></td><td>{alarm_data['timestamp']}</td></tr>
            <tr><td><strong>Mức độ</strong></td><td>{alarm_data['severity'].upper()}</td></tr>
            <tr><td><strong>Doanh thu hiện tại</strong></td><td>{alarm_data['current_revenue']:,.0f} VNĐ</td></tr>
            <tr><td><strong>Doanh thu trước đó</strong></td><td>{alarm_data['previous_revenue']:,.0f} VNĐ</td></tr>
            <tr><td><strong>Thay đổi</strong></td><td style="color:red">{alarm_data['change_pct']}%</td></tr>
        </table>
        <p>{alarm_data.get('natural_message', alarm_data['message'])}</p>
        """

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json={
                    "personalizations": [{"to": [{"email": e} for e in ALERT_RECIPIENTS]}],
                    "from": {"email": SENDGRID_FROM_EMAIL},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_content}],
                },
                headers={
                    "Authorization": f"Bearer {SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            if response.status_code in (200, 202):
                logger.info("Alarm email sent successfully")
            else:
                logger.error(f"SendGrid error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Email sending error: {e}")


async def _push_sse_alarm(alarm_data: Dict[str, Any]):
    """Đẩy alarm event qua SSE cho Frontend."""
    global _alarm_event_queue
    if _alarm_event_queue is not None:
        try:
            await _alarm_event_queue.put({
                "event": "alarm",
                "data": json.dumps(alarm_data, ensure_ascii=False, default=str),
            })
            logger.info("Alarm event pushed to SSE queue")
        except Exception as e:
            logger.error(f"SSE push error: {e}")
    else:
        logger.info("No SSE queue configured, alarm event not pushed")
