"""
Dashboard Cache Service
Tự động build và lưu cache dashboard vào các mốc 07:00, 10:00, 13:00, 16:00 (Asia/Ho_Chi_Minh).
Cache được lưu vào bảng public.dashboard_cache trong Supabase.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from backend.services.db_executor import fetch_one, upsert_via_rest

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
CACHE_KEY = "dashboard_main"
# Cache hết hạn sau 3 tiếng (khoảng cách giữa 2 mốc cập nhật)
CACHE_TTL_HOURS = 3


# ============================================================
# Public API
# ============================================================

async def build_and_cache_dashboard() -> Dict[str, Any]:
    """
    Build toàn bộ dashboard data và lưu vào cache.
    Được gọi bởi APScheduler vào 07:00, 10:00, 13:00, 16:00.
    """
    now_vn = datetime.now(TIMEZONE)
    slot = _get_cache_slot(now_vn)
    logger.info(f"[DashboardCache] Building cache at slot {slot} ({now_vn.strftime('%H:%M')} ICT)")

    try:
        data = await _build_dashboard_data()
        await _save_cache(data, slot)
        logger.info(f"[DashboardCache] Cache saved successfully for slot {slot}")
        return data
    except Exception as e:
        logger.error(f"[DashboardCache] Failed to build cache: {e}", exc_info=True)
        raise


async def get_cached_dashboard() -> Optional[Dict[str, Any]]:
    """
    Trả về cache nếu còn hạn, ngược lại trả về None.
    """
    try:
        result = await fetch_one(
            f"SELECT data, cached_at, expires_at, cache_slot FROM dashboard_cache WHERE cache_key = '{CACHE_KEY}'"
        )
        if not result:
            logger.info("[DashboardCache] No cache found")
            return None

        expires_at = result.get("expires_at")
        if isinstance(expires_at, str):
            from dateutil.parser import parse as parse_dt
            expires_at = parse_dt(expires_at)

        now_utc = datetime.utcnow()
        if expires_at:
            # Normalize to naive UTC for comparison
            if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo:
                expires_naive = expires_at.replace(tzinfo=None)
            else:
                expires_naive = expires_at

            if expires_naive > now_utc:
                logger.info(f"[DashboardCache] Cache hit (slot: {result.get('cache_slot')})")
                data = result["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                return data

        logger.info("[DashboardCache] Cache expired")
        return None
    except Exception as e:
        logger.warning(f"[DashboardCache] Error reading cache: {e}")
        return None


async def get_cache_status() -> Dict[str, Any]:
    """Trả về trạng thái cache hiện tại."""
    try:
        result = await fetch_one(
            f"SELECT cache_key, cached_at, expires_at, cache_slot FROM dashboard_cache WHERE cache_key = '{CACHE_KEY}'"
        )
        if not result:
            return {"status": "no_cache", "message": "Chưa có cache nào được tạo"}

        now_vn = datetime.now(TIMEZONE)
        expires_at = result.get("expires_at")
        if isinstance(expires_at, str):
            from dateutil.parser import parse as parse_dt
            expires_at = parse_dt(expires_at)

        now_utc = datetime.utcnow()
        if hasattr(expires_at, 'tzinfo') and expires_at.tzinfo:
            expires_naive = expires_at.replace(tzinfo=None)
        else:
            expires_naive = expires_at

        is_valid = expires_naive and expires_naive > now_utc
        next_slot = _get_next_slot(now_vn, ["07:00", "10:00", "13:00", "16:00"])

        return {
            "status": "valid" if is_valid else "expired",
            "cache_slot": result.get("cache_slot"),
            "cached_at": str(result.get("cached_at")),
            "expires_at": str(expires_at),
            "is_valid": is_valid,
            "next_scheduled_refresh": next_slot,
            "current_time_vn": now_vn.strftime("%Y-%m-%d %H:%M:%S ICT"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============================================================
# Private helpers
# ============================================================

def _get_cache_slot(dt: datetime) -> str:
    """Xác định slot cache dựa trên giờ hiện tại."""
    hour = dt.hour
    if hour < 10:
        return "07:00"
    elif hour < 13:
        return "10:00"
    elif hour < 16:
        return "13:00"
    else:
        return "16:00"


def _get_next_slot(now: datetime, slots: list) -> str:
    """Xác định slot tiếp theo."""
    current_hm = now.strftime("%H:%M")
    for slot in slots:
        if slot > current_hm:
            return slot
    return slots[0] + " (ngày mai)"


async def _save_cache(data: Dict[str, Any], slot: str):
    """Lưu data vào bảng dashboard_cache qua upsert_via_rest."""
    now_utc = datetime.utcnow()
    expires_at = now_utc + timedelta(hours=CACHE_TTL_HOURS)
    data_json = json.dumps(data, ensure_ascii=False, default=str)

    await upsert_via_rest(
        table="dashboard_cache",
        data={
            "cache_key": CACHE_KEY,
            "data": data_json,
            "cached_at": now_utc.isoformat(),
            "expires_at": expires_at.isoformat(),
            "cache_slot": slot,
        },
        schema="public",
    )


async def _build_dashboard_data() -> Dict[str, Any]:
    """Build toàn bộ dashboard data từ database."""
    from backend.api.routes.dashboard_router import (
        _get_revenue_summary,
        _get_monthly_revenue,
        _get_top_products,
        _get_customer_segments,
        _get_daily_revenue_trend,
        _get_channel_distribution,
        _get_competitor_overview,
    )

    logger.info("[DashboardCache] Fetching all dashboard datasets...")

    import asyncio
    (
        revenue_summary,
        monthly_revenue,
        top_products,
        customer_segments,
        daily_revenue,
        channel_dist,
        competitor,
    ) = await asyncio.gather(
        _get_revenue_summary(),
        _get_monthly_revenue(),
        _get_top_products(),
        _get_customer_segments(),
        _get_daily_revenue_trend(),
        _get_channel_distribution(),
        _get_competitor_overview(),
    )

    now_vn = datetime.now(TIMEZONE)
    return {
        "revenue_summary": revenue_summary,
        "monthly_revenue": monthly_revenue,
        "top_products": top_products,
        "customer_segments": customer_segments,
        "daily_revenue": daily_revenue,
        "channel_distribution": channel_dist,
        "competitor_overview": competitor,
        "generated_at": now_vn.isoformat(),
        "cache_slot": _get_cache_slot(now_vn),
    }
