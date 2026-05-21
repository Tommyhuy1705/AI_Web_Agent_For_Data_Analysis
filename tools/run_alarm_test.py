#!/usr/bin/env python3
"""Direct alarm test - bypass API"""
import asyncio
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

async def run_alarm():
    from backend.services.db_executor import get_pool
    pool = await get_pool()
    
    from backend.services.alarm_monitor import check_hourly_revenue_alarm
    print("\n" + "="*60)
    print("RUNNING ALARM CHECK DIRECTLY")
    print("="*60)
    await check_hourly_revenue_alarm()
    print("="*60)
    print("ALARM CHECK COMPLETE")
    print("="*60)
    
    await pool.close()

asyncio.run(run_alarm())
