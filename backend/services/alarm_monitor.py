"""
Alarm Monitor Service
Logic so sánh snapshot 1h cho tính năng Proactive Alarm.
Chạy mỗi 60 phút qua APScheduler.

Flow:
1. Query tổng doanh thu giờ vừa qua từ fact_sales (public schema)
2. So sánh với value trong hourly_snapshot
3. Nếu giảm > 15%: UPSERT value mới -> Gọi webhook Dify -> SendGrid email -> SSE thông báo

SendGrid Integration:
- Gửi email cảnh báo khi alarm triggered
- Bao gồm AI-generated insight về nguyên nhân
- Link tới Dashboard để xem chi tiết
- Retry logic (tối đa 3 lần)
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
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
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@sia-agent.com")
ALERT_RECIPIENTS = [e.strip() for e in os.getenv("ALERT_RECIPIENTS", "admin@company.com").split(",")]
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Retry configuration
EMAIL_MAX_RETRIES = 3
EMAIL_RETRY_DELAY = 2  # seconds

# SSE event queue (sẽ được inject từ main.py)
_alarm_event_queue = None


def set_alarm_event_queue(queue):
    """Set event queue cho SSE alarm notifications."""
    global _alarm_event_queue
    _alarm_event_queue = queue


def _utc_now_iso() -> str:
    """Return ISO-8601 timestamp in UTC with timezone info."""
    return datetime.now(timezone.utc).isoformat()


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
    """Query tổng doanh thu trong 1 giờ gần nhất từ fact_sales (public schema)."""
    try:
        result = await fetch_one("""
            SELECT COALESCE(SUM(total_amount), 0) as total_revenue
            FROM fact_sales
            WHERE created_at >= NOW() - INTERVAL '1 hour'
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
                "last_updated": _utc_now_iso(),
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
    1. Sinh AI insight về nguyên nhân
    2. Gọi webhook Dify để sinh câu cảnh báo tự nhiên
    3. Gửi email qua SendGrid (với retry)
    4. Đẩy thông báo SSE lên Frontend
    """
    alarm_data = {
        "type": "revenue_alarm",
        "severity": "critical" if change_pct < -30 else "warning",
        "current_revenue": current_revenue,
        "previous_revenue": previous_revenue,
        "change_pct": round(change_pct, 2),
        "timestamp": _utc_now_iso(),
        "message": f"Cảnh báo: Doanh thu giảm {abs(change_pct):.1f}% so với giờ trước "
                   f"(Hiện tại: {current_revenue:,.0f} VNĐ, Trước đó: {previous_revenue:,.0f} VNĐ)"
    }

    # 0. Enrich với dữ liệu đối thủ từ TinyFish (nếu có)
    try:
        from backend.services.tinyfish_service import get_competitor_context_for_alarm
        competitor_context = await get_competitor_context_for_alarm()
        if competitor_context:
            alarm_data["competitor_context"] = competitor_context
            logger.info("Alarm enriched with competitor context from TinyFish")
    except Exception as e:
        logger.debug(f"Could not enrich alarm with competitor data: {e}")

    # 1. Sinh AI insight về nguyên nhân có thể (bao gồm competitor context)
    ai_insight = await _generate_alarm_insight(alarm_data)
    if ai_insight:
        alarm_data["ai_insight"] = ai_insight

    # 2. Gọi Dify webhook (nếu có cấu hình)
    natural_message = await _call_dify_alarm_webhook(alarm_data)
    if natural_message:
        alarm_data["natural_message"] = natural_message

    # 3. Gửi email qua SendGrid (với retry logic)
    email_sent = await _send_alarm_email_with_retry(alarm_data)
    alarm_data["email_sent"] = email_sent

    # 4. Đẩy SSE event
    await _push_sse_alarm(alarm_data)

    logger.info(f"Alarm triggered - Email: {'sent' if email_sent else 'skipped'}, SSE: pushed")


async def _generate_alarm_insight(alarm_data: Dict[str, Any]) -> Optional[str]:
    """Sinh AI insight về nguyên nhân có thể gây giảm doanh thu."""
    try:
        from backend.services.llm_client import chat_completion, is_configured

        if not is_configured():
            logger.info("LLM not configured, skipping alarm insight generation")
            return None

        content = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia phân tích doanh thu. Đưa ra 2-3 nguyên nhân có thể và 1-2 hành động khuyến nghị. Ngắn gọn, chuyên nghiệp, bằng tiếng Việt."
                },
                {
                    "role": "user",
                    "content": f"Doanh thu giảm {abs(alarm_data['change_pct']):.1f}%. "
                               f"Hiện tại: {alarm_data['current_revenue']:,.0f} VNĐ, "
                               f"Trước đó: {alarm_data['previous_revenue']:,.0f} VNĐ. "
                               f"Mức độ: {alarm_data['severity']}. "
                               + (f"\n\nDữ liệu đối thủ cạnh tranh: {alarm_data.get('competitor_context', 'Không có dữ liệu')}" if alarm_data.get('competitor_context') else "")
                               + f"\nPhân tích nguyên nhân có thể và đề xuất hành động."
                },
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return content
    except Exception as e:
        logger.warning(f"Could not generate AI insight for alarm: {e}")
        return None


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


async def _send_alarm_email_with_retry(alarm_data: Dict[str, Any]) -> bool:
    """
    Gửi email cảnh báo qua SendGrid API với retry logic.
    Returns True nếu gửi thành công, False nếu skip hoặc fail.
    """
    if not SENDGRID_API_KEY:
        logger.info("SendGrid API key not configured, skipping email")
        return False

    import asyncio

    for attempt in range(1, EMAIL_MAX_RETRIES + 1):
        try:
            success = await _send_alarm_email(alarm_data)
            if success:
                logger.info(f"Alarm email sent successfully (attempt {attempt})")
                return True
            else:
                logger.warning(f"Email send attempt {attempt} failed")
        except Exception as e:
            logger.error(f"Email send attempt {attempt} error: {e}")

        if attempt < EMAIL_MAX_RETRIES:
            await asyncio.sleep(EMAIL_RETRY_DELAY * attempt)

    logger.error(f"Failed to send alarm email after {EMAIL_MAX_RETRIES} attempts")
    return False


async def _send_alarm_email(alarm_data: Dict[str, Any]) -> bool:
    """Gửi email cảnh báo qua SendGrid API."""
    severity_emoji = "🔴" if alarm_data["severity"] == "critical" else "🟡"
    severity_color = "#DC2626" if alarm_data["severity"] == "critical" else "#F59E0B"
    subject = f"{severity_emoji} SIA Alert: Doanh thu giảm {abs(alarm_data['change_pct'])}%"

    # AI insight section
    ai_insight_html = ""
    if alarm_data.get("ai_insight"):
        ai_insight_html = f"""
        <div style="background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 12px; margin: 16px 0; border-radius: 4px;">
            <strong>🤖 AI Insight:</strong>
            <p style="margin: 8px 0 0 0; white-space: pre-wrap;">{alarm_data['ai_insight']}</p>
        </div>
        """

    # Natural message from Dify
    natural_msg_html = ""
    if alarm_data.get("natural_message"):
        natural_msg_html = f"""
        <div style="background: #EFF6FF; border-left: 4px solid #3B82F6; padding: 12px; margin: 16px 0; border-radius: 4px;">
            <strong>💬 Agent Message:</strong>
            <p style="margin: 8px 0 0 0;">{alarm_data['natural_message']}</p>
        </div>
        """

    html_content = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #fff;">
        <!-- Header -->
        <div style="background: {severity_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h1 style="margin: 0; font-size: 20px;">{severity_emoji} Cảnh báo Doanh thu Bất thường</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 14px;">
                {alarm_data['timestamp'][:19].replace('T', ' ')} UTC
            </p>
        </div>

        <!-- Body -->
        <div style="padding: 24px; border: 1px solid #E5E7EB; border-top: none; border-radius: 0 0 8px 8px;">
            <!-- KPI Cards -->
            <div style="display: flex; gap: 12px; margin-bottom: 20px;">
                <div style="flex: 1; background: #FEF2F2; padding: 16px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: #666;">Doanh thu hiện tại</div>
                    <div style="font-size: 20px; font-weight: bold; color: #DC2626;">
                        {alarm_data['current_revenue']:,.0f} VNĐ
                    </div>
                </div>
                <div style="flex: 1; background: #F3F4F6; padding: 16px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: #666;">Doanh thu trước đó</div>
                    <div style="font-size: 20px; font-weight: bold; color: #374151;">
                        {alarm_data['previous_revenue']:,.0f} VNĐ
                    </div>
                </div>
            </div>

            <!-- Change indicator -->
            <div style="text-align: center; margin: 16px 0;">
                <span style="background: {severity_color}; color: white; padding: 8px 16px; border-radius: 20px; font-size: 16px; font-weight: bold;">
                    ↓ {abs(alarm_data['change_pct']):.1f}% giảm
                </span>
            </div>

            <!-- Detail table -->
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr style="border-bottom: 1px solid #E5E7EB;">
                    <td style="padding: 10px; font-weight: bold; color: #374151;">Mức độ</td>
                    <td style="padding: 10px; color: {severity_color}; font-weight: bold;">
                        {alarm_data['severity'].upper()}
                    </td>
                </tr>
                <tr style="border-bottom: 1px solid #E5E7EB;">
                    <td style="padding: 10px; font-weight: bold; color: #374151;">Ngưỡng cảnh báo</td>
                    <td style="padding: 10px;">{ALARM_THRESHOLD_PCT}%</td>
                </tr>
                <tr style="border-bottom: 1px solid #E5E7EB;">
                    <td style="padding: 10px; font-weight: bold; color: #374151;">Chênh lệch</td>
                    <td style="padding: 10px; color: red;">
                        {alarm_data['current_revenue'] - alarm_data['previous_revenue']:,.0f} VNĐ
                    </td>
                </tr>
            </table>

            {ai_insight_html}
            {natural_msg_html}

            <!-- CTA Button -->
            <div style="text-align: center; margin: 24px 0;">
                <a href="{FRONTEND_URL}/dashboard"
                   style="background: #3B82F6; color: white; padding: 12px 32px; border-radius: 8px;
                          text-decoration: none; font-weight: bold; display: inline-block;">
                    📊 Xem Dashboard Chi tiết
                </a>
            </div>

            <!-- Message -->
            <p style="color: #6B7280; font-size: 13px; text-align: center; margin-top: 24px;">
                {alarm_data.get('natural_message', alarm_data['message'])}
            </p>
        </div>

        <!-- Footer -->
        <div style="text-align: center; padding: 16px; color: #9CA3AF; font-size: 11px;">
            SIA | Automated Alert System<br>
            <a href="{FRONTEND_URL}" style="color: #6B7280;">Truy cập hệ thống</a>
        </div>
    </div>
    """

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            json={
                "personalizations": [{"to": [{"email": e} for e in ALERT_RECIPIENTS]}],
                "from": {"email": SENDGRID_FROM_EMAIL, "name": "SIA"},
                "subject": subject,
                "content": [{"type": "text/html", "value": html_content}],
            },
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        if response.status_code in (200, 202):
            return True
        else:
            logger.error(f"SendGrid error: {response.status_code} - {response.text}")
            return False


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


async def check_smart_alarm_morning():
    """
    Smart Alarm chạy lúc 08:00 sáng mỗi ngày.
    So sánh doanh thu hiện tại với baseline 18:00 hôm qua.
    Chỉ gửi cảnh báo nếu % thay đổi vượt ngưỡng ALARM_THRESHOLD_PCT (mặc định 15%).
    """
    logger.info("[SmartAlarm] Running morning smart alarm check at 08:00...")
    try:
        # Lấy doanh thu hiện tại (từ đầu ngày đến 08:00)
        current_revenue = await _get_current_hour_revenue()
        if current_revenue is None:
            logger.warning("[SmartAlarm] Could not get current revenue, skipping.")
            return

        # Lấy snapshot baseline (18:00 hôm qua)
        snapshot = await _get_previous_snapshot("morning_baseline_revenue")
        if snapshot is None:
            # Lần đầu chạy: lưu snapshot và không gửi alarm
            await _upsert_snapshot(
                metric_name="morning_baseline_revenue",
                current_value=current_revenue,
                previous_value=0,
                change_pct=0,
            )
            logger.info(f"[SmartAlarm] First run: saved baseline = {current_revenue:,.0f} VND")
            return

        baseline_revenue = float(snapshot.get("value", 0))
        if baseline_revenue <= 0:
            logger.warning("[SmartAlarm] Baseline revenue is 0, skipping alarm check.")
            return

        change_pct = ((current_revenue - baseline_revenue) / baseline_revenue) * 100
        logger.info(
            f"[SmartAlarm] Baseline: {baseline_revenue:,.0f} VND | "
            f"Current: {current_revenue:,.0f} VND | "
            f"Change: {change_pct:.2f}%"
        )

        # Chỉ trigger alarm nếu vượt ngưỡng
        if abs(change_pct) >= ALARM_THRESHOLD_PCT:
            logger.warning(f"[SmartAlarm] ALARM TRIGGERED! Change = {change_pct:.2f}%")
            await _trigger_alarm(
                current_revenue=current_revenue,
                previous_revenue=baseline_revenue,
                change_pct=change_pct,
            )
        else:
            logger.info(
                f"[SmartAlarm] No alarm needed. "
                f"Change {change_pct:.2f}% < threshold {ALARM_THRESHOLD_PCT}%"
            )

        # Cập nhật baseline cho ngày hôm sau
        await _upsert_snapshot(
            metric_name="morning_baseline_revenue",
            current_value=current_revenue,
            previous_value=baseline_revenue,
            change_pct=change_pct,
        )

    except Exception as e:
        logger.error(f"[SmartAlarm] Error in morning smart alarm: {e}", exc_info=True)
