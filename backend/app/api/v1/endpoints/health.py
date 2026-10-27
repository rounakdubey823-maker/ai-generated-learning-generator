"""
/api/v1/health — detailed health endpoint.
"""

import time
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter()

# Record the server start time so we can expose uptime
_START_TIME = time.time()


async def _check_database(db: AsyncSession) -> Dict[str, Any]:
    """Ping the database and return its status."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "detail": str(exc)}


@router.get(
    "",
    summary="Detailed health check",
    response_description="Health status of the service and its dependencies",
)
async def health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns a structured health report including:
    - Overall service status
    - Uptime in seconds
    - Database connectivity
    - Environment and version info
    """
    db_status = await _check_database(db)
    uptime_seconds = round(time.time() - _START_TIME, 1)

    overall = "ok" if db_status["status"] == "ok" else "degraded"

    return {
        "status": overall,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": uptime_seconds,
        "dependencies": {
            "database": db_status,
        },
    }
