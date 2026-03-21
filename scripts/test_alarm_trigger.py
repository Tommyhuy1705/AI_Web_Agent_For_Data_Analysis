"""
Test Script: Alarm System Trigger
Set hourly_snapshot cao hơn doanh thu thực tế để kích hoạt alarm và gửi email.
Kết quả mong đợi: Revenue drop -66.67%, email gửi qua SendGrid HTTP 202.
"""
import asyncio
import sys
import logging
import httpx
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

import psycopg2
from datetime import datetime, timezone

DB_URL = os.getenv("SUPABASE_DATABASE_URL", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

def set_high_snapshot(multiplier=3.0):
    """Set snapshot to multiplier * current revenue to trigger alarm."""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0) FROM fact_sales 
        WHERE created_at >= NOW() - INTERVAL '1 hour'
    """)
    current_1h = float(cursor.fetchone()[0])
    high_value = current_1h * multiplier if current_1h > 0 else 3_000_000_000.0
    cursor.execute("""
        UPDATE hourly_snapshot SET value=%s, previous_value=%s, change_pct=0, last_updated=%s
        WHERE metric_name='hourly_revenue'
    """, (high_value, high_value, datetime.now(timezone.utc).isoformat()))
    if cursor.rowcount == 0:
        cursor.execute("""
            INSERT INTO hourly_snapshot (metric_name, value, previous_value, change_pct, last_updated)
            VALUES ('hourly_revenue', %s, %s, 0, %s)
        """, (high_value, high_value, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    expected_change = ((current_1h - high_value) / high_value * 100) if high_value > 0 else 0
    print(f"✓ Snapshot set to {high_value:,.0f} VND ({multiplier}x current)")
    print(f"  Current 1h revenue: {current_1h:,.0f} VND")
    print(f"  Expected change: {expected_change:.1f}%")
    cursor.close()
    conn.close()

async def run_alarm_check():
    """Patch upsert and run alarm check."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    import backend.services.db_executor as db_mod

    async def patched_upsert(table, data, schema="public", on_conflict=""):
        headers = {
            "apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json", "Prefer": "return=representation"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            metric = data.get("metric_name", "")
            resp = await client.patch(
                f"{SUPABASE_URL}/rest/v1/{table}?metric_name=eq.{metric}",
                json=data, headers=headers
            )
            if resp.status_code in (200, 204):
                return data
            resp = await client.post(f"{SUPABASE_URL}/rest/v1/{table}", json=data, headers=headers)
            if resp.status_code in (200, 201):
                return resp.json()[0] if resp.json() else data
            raise Exception(f"Upsert error {resp.status_code}: {resp.text[:200]}")

    db_mod.upsert_via_rest = patched_upsert
    from backend.services.db_executor import get_pool
    await get_pool()
    from backend.services.alarm_monitor import check_hourly_revenue_alarm
    await check_hourly_revenue_alarm()

if __name__ == "__main__":
    print("=== ALARM SYSTEM TEST ===")
    set_high_snapshot(multiplier=3.0)
    print("\nRunning alarm check...")
    asyncio.run(run_alarm_check())
