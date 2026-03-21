"""
SIA - Backend Main Application
FastAPI App with SSE config, APScheduler for Proactive Alarm,
and CORS configuration for Next.js frontend.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env: try backend/.env first, then root .env
_env_path = Path(__file__).parent / ".env"
_root_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)
elif _root_env_path.exists():
    load_dotenv(_root_env_path, override=True)
else:
    load_dotenv()  # fallback to cwd

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.api.routes.chat_router import router as chat_router
from backend.api.routes.sql_proxy import router as sql_router
from backend.api.routes.predict_router import router as predict_router
from backend.api.routes.dashboard_router import router as dashboard_router
from backend.api.routes.market_intel_router import router as market_intel_router
from backend.api.routes.chat_history_router import router as chat_history_router
from backend.services.db_executor import get_pool, close_pool
from backend.services.alarm_monitor import (
    check_hourly_revenue_alarm,
    check_smart_alarm_morning,
    set_alarm_event_queue,
)
from backend.services.dbt_runner import daily_dbt_run
from backend.services.monthly_report import generate_monthly_report
from backend.services.tinyfish_service import is_configured as tinyfish_configured

# ============================================================
# Logging Configuration
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# APScheduler Configuration
# ============================================================
scheduler = AsyncIOScheduler()

# SSE Event Queue cho alarm notifications
alarm_event_queue = asyncio.Queue()


# ============================================================
# Application Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("=" * 60)
    logger.info("SIA - Backend Starting...")
    logger.info("=" * 60)

    # Initialize database connection pool
    try:
        pool = await get_pool()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.warning(f"Database connection failed (will retry on demand): {e}")

    # Set alarm event queue
    set_alarm_event_queue(alarm_event_queue)

    # ── Smart Alarm: 08:00 sáng mỗi ngày (Asia/Ho_Chi_Minh) ──────────────────
    # So sánh doanh thu cửa sổ 18:00 hôm trước → 08:00 hôm nay vs baseline 7 ngày
    # Chỉ cảnh báo khi biến động vượt ngưỡng ±15%
    scheduler.add_job(
        check_smart_alarm_morning,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Ho_Chi_Minh"),
        id="smart_alarm_morning",
        name="Smart Alarm Morning Check (08:00 ICT)",
        replace_existing=True,
    )

    # ── Scheduled Dashboard Cache: 07:00, 10:00, 13:00, 16:00 (ICT) ──────────────
    # Build và cache toàn bộ dashboard data vào các mốc giờ cố định
    from backend.services.dashboard_cache_service import build_and_cache_dashboard
    for _slot_hour in [7, 10, 13, 16]:
        scheduler.add_job(
            build_and_cache_dashboard,
            trigger=CronTrigger(hour=_slot_hour, minute=0, timezone="Asia/Ho_Chi_Minh"),
            id=f"dashboard_cache_{_slot_hour:02d}00",
            name=f"Dashboard Cache Refresh ({_slot_hour:02d}:00 ICT)",
            replace_existing=True,
        )
    logger.info("Dashboard cache scheduled at 07:00, 10:00, 13:00, 16:00 ICT")

    # dbt run - TEST MODE: chạy mỗi 2 phút (đổi lại CronTrigger(hour=0, minute=0) sau khi test)
    scheduler.add_job(
        daily_dbt_run,
        trigger=IntervalTrigger(minutes=2),
        id="daily_dbt_run",
        name="dbt Run (every 2 min - TEST MODE)",
        replace_existing=True,
    )

    # Monthly strategy report - ngày 1 mỗi tháng lúc 01:00 UTC
    scheduler.add_job(
        generate_monthly_report,
        trigger=CronTrigger(day=1, hour=1, minute=0),
        id="monthly_strategy_report",
        name="Monthly Strategy Report (1st of month)",
        replace_existing=True,
    )

    # TinyFish Market Intel Crawl - mỗi 6 giờ (nếu đã cấu hình API key)
    if tinyfish_configured():
        from backend.services.tinyfish_service import run_competitor_crawl
        scheduler.add_job(
            run_competitor_crawl,
            trigger=IntervalTrigger(hours=6),
            id="tinyfish_market_crawl",
            name="TinyFish Market Intelligence Crawl (every 6h)",
            replace_existing=True,
        )
        logger.info("TinyFish market crawl scheduled (every 6 hours)")
    else:
        logger.info("TinyFish not configured - market crawl disabled")

    scheduler.start()
    logger.info("APScheduler started - Smart Alarm (08:00) + Dashboard Cache (07/10/13/16h) + dbt + Monthly report + Market Intel enabled")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    await close_pool()
    logger.info("Backend shutdown complete")


# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="SIA API",
    description="AI Web Agent for Enterprise Data Analysis - Backend API",
    version="1.0.0",
    lifespan=lifespan,
)

# ============================================================
# CORS Middleware (cho Next.js Frontend)
# ============================================================
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
ALLOWED_ORIGINS = [
    FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
]

# In development/demo, allow all origins for cross-domain access
# In production, restrict to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ============================================================
# Include Routers
# ============================================================
app.include_router(chat_router)
app.include_router(sql_router)
app.include_router(predict_router)
app.include_router(dashboard_router)
app.include_router(market_intel_router)
app.include_router(chat_history_router)


# ============================================================
# Root & Health Endpoints
# ============================================================
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "SIA API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    from backend.services.db_executor import health_check
    from backend.services.llm_client import get_provider, get_model, is_configured
    db_status = await health_check()
    return {
        "status": "healthy",
        "database": db_status,
        "llm": {
            "provider": get_provider(),
            "model": get_model(),
            "configured": is_configured(),
        },
        "tinyfish": {
            "configured": tinyfish_configured(),
            "purpose": "Market Intelligence (Competitor Tracking)",
        },
        "scheduler": {
            "running": scheduler.running,
            "jobs": len(scheduler.get_jobs()),
        },
    }


@app.get("/api/alarm/stream")
async def alarm_stream():
    """
    SSE endpoint cho alarm notifications.
    Frontend subscribe để nhận cảnh báo real-time.
    """
    from fastapi.responses import StreamingResponse
    import json

    async def event_generator():
        while True:
            try:
                # Wait for alarm events (timeout 30s để keep-alive)
                event = await asyncio.wait_for(
                    alarm_event_queue.get(), timeout=30
                )
                yield f"event: {event['event']}\ndata: {event['data']}\n\n"
            except asyncio.TimeoutError:
                # Send keep-alive ping
                yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"
            except Exception as e:
                logger.error(f"Alarm stream error: {e}")
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# Run with uvicorn
# ============================================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
