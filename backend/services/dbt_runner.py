"""
dbt Runner Service
Chạy dbt run/test qua subprocess.
Được gọi bởi APScheduler cron job mỗi ngày lúc 00:00 UTC.

Flow:
1. APScheduler trigger lúc midnight
2. Chạy `dbt run` trong thư mục data_pipeline/dbt_transform
3. Log kết quả (success/fail)
4. (Optional) Chạy `dbt test` sau khi run thành công
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# dbt project path (relative to repo root)
_repo_root = Path(__file__).parent.parent.parent  # backend/services -> backend -> repo root
DBT_PROJECT_DIR = os.getenv(
    "DBT_PROJECT_DIR",
    str(_repo_root / "data_pipeline" / "dbt_transform")
)

# dbt command (can be overridden via env)
DBT_COMMAND = os.getenv("DBT_COMMAND", "dbt")


async def run_dbt_command(
    command: str = "run",
    project_dir: Optional[str] = None,
    profiles_dir: Optional[str] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """
    Chạy dbt command bất đồng bộ.

    Args:
        command: dbt command (run, test, build, etc.)
        project_dir: Đường dẫn tới dbt project
        profiles_dir: Đường dẫn tới profiles.yml
        timeout: Timeout in seconds

    Returns:
        Dict chứa status, output, error, duration
    """
    project_dir = project_dir or DBT_PROJECT_DIR
    profiles_dir = profiles_dir or project_dir

    cmd = [
        DBT_COMMAND,
        command,
        "--project-dir", project_dir,
        "--profiles-dir", profiles_dir,
    ]

    start_time = datetime.utcnow()
    logger.info(f"Running dbt command: {' '.join(cmd)}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            duration = (datetime.utcnow() - start_time).total_seconds()
            result = {
                "status": "timeout",
                "command": command,
                "duration_seconds": duration,
                "output": "",
                "error": f"dbt {command} timed out after {timeout}s",
                "return_code": -1,
                "timestamp": start_time.isoformat(),
            }
            logger.error(f"dbt {command} timeout after {timeout}s")
            return result

        duration = (datetime.utcnow() - start_time).total_seconds()
        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        success = process.returncode == 0

        result = {
            "status": "success" if success else "failed",
            "command": command,
            "duration_seconds": round(duration, 2),
            "output": stdout_str[-2000:],  # Last 2000 chars
            "error": stderr_str[-1000:] if stderr_str else "",
            "return_code": process.returncode,
            "timestamp": start_time.isoformat(),
        }

        if success:
            logger.info(f"dbt {command} completed successfully in {duration:.1f}s")
        else:
            logger.error(f"dbt {command} failed (code {process.returncode}): {stderr_str[:200]}")

        return result

    except FileNotFoundError:
        duration = (datetime.utcnow() - start_time).total_seconds()
        result = {
            "status": "error",
            "command": command,
            "duration_seconds": round(duration, 2),
            "output": "",
            "error": f"dbt command not found. Make sure dbt is installed and in PATH. "
                     f"Tried: {DBT_COMMAND}",
            "return_code": -1,
            "timestamp": start_time.isoformat(),
        }
        logger.error(f"dbt not found: {DBT_COMMAND}")
        return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        result = {
            "status": "error",
            "command": command,
            "duration_seconds": round(duration, 2),
            "output": "",
            "error": str(e),
            "return_code": -1,
            "timestamp": start_time.isoformat(),
        }
        logger.error(f"dbt {command} error: {e}", exc_info=True)
        return result


async def daily_dbt_run():
    """
    Cron job chạy mỗi ngày lúc 00:00 UTC.
    Flow: dbt run -> (nếu thành công) dbt test
    """
    logger.info("=" * 50)
    logger.info("DBT CRON JOB: Starting daily dbt run...")
    logger.info("=" * 50)

    # Step 1: dbt run
    run_result = await run_dbt_command("run")
    logger.info(f"dbt run result: {run_result['status']}")

    # Step 2: dbt test (chỉ chạy nếu run thành công)
    if run_result["status"] == "success":
        test_result = await run_dbt_command("test")
        logger.info(f"dbt test result: {test_result['status']}")
    else:
        test_result = {"status": "skipped", "error": "Skipped because dbt run failed"}
        logger.warning("dbt test skipped because dbt run failed")

    # Log summary
    logger.info(f"DBT CRON JOB COMPLETE: run={run_result['status']}, test={test_result['status']}")

    return {
        "run": run_result,
        "test": test_result,
    }
