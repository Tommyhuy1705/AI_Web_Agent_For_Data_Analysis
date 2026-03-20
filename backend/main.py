"""
Omni-Revenue Agent - Backend Main Application
FastAPI App with SSE config, APScheduler for Proactive Alarm,
and CORS configuration for Next.js frontend.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)
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
from backend.services.db_executor import get_pool, close_pool
from backend.services.alarm_monitor import (
    check_hourly_revenue_alarm,
    set_alarm_event_queue,
)
from backend.services.dbt_runner import daily_dbt_run
from backend.services.monthly_report import generate_monthly_report

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
    logger.info("OMNI-REVENUE AGENT - Backend Starting...")
    logger.info("=" * 60)

    # Initialize database connection pool
    try:
        pool = await get_pool()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.warning(f"Database connection failed (will retry on demand): {e}")

    # Set alarm event queue
    set_alarm_event_queue(alarm_event_queue)

    # Start APScheduler - Proactive Alarm mỗi 60 phút
    scheduler.add_job(
        check_hourly_revenue_alarm,
        trigger=IntervalTrigger(minutes=60),
        id="hourly_alarm_check",
        name="Hourly Revenue Alarm Check",
        replace_existing=True,
    )

    # dbt run cron job - mỗi ngày lúc 00:00 UTC
    scheduler.add_job(
        daily_dbt_run,
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_dbt_run",
        name="Daily dbt Run (midnight)",
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

    scheduler.start()
    logger.info("APScheduler started - Hourly alarm + Daily dbt + Monthly report enabled")

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
    title="Omni-Revenue Agent API",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
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


# ============================================================
# Root & Health Endpoints
# ============================================================
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Omni-Revenue Agent API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    from backend.services.db_executor import health_check
    db_status = await health_check()
    return {
        "status": "healthy",
        "database": db_status,
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
