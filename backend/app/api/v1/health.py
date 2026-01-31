"""Health check endpoint with dependency verification."""
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from celery import Celery

from app.db.session import sync_engine
from app.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    """
    Health check endpoint with dependency verification.

    Checks:
    - MySQL connectivity (SELECT 1 query)
    - Redis connectivity (PING command)
    - Celery worker availability

    Returns:
        JSON response with overall status and individual check results
    """
    checks = {}
    overall_healthy = True

    # Check MySQL
    try:
        with Session(sync_engine) as session:
            session.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
    except Exception as e:
        logger.warning(f"MySQL health check failed: {e}")
        checks["mysql"] = f"error: {type(e).__name__}"
        overall_healthy = False

    # Check Redis
    try:
        import redis
        settings = get_settings()
        # Parse Redis URL to get host and port
        # Format: redis://host:port/db or redis://host:port
        redis_url = settings.redis_url
        if redis_url.startswith("redis://"):
            parts = redis_url.replace("redis://", "").split("/")
            host_port = parts[0].split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 6379

            r = redis.Redis(host=host, port=port, socket_connect_timeout=2)
            r.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "error: unsupported Redis URL format"
            overall_healthy = False
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        checks["redis"] = f"error: {type(e).__name__}"
        overall_healthy = False

    # Check Celery workers
    try:
        settings = get_settings()
        celery_app = Celery(broker=settings.redis_url)
        inspect = celery_app.control.inspect(timeout=2.0)
        active_workers = inspect.active()

        if active_workers and len(active_workers) > 0:
            checks["celery"] = f"ok ({len(active_workers)} workers)"
        else:
            checks["celery"] = "error: no active workers"
            overall_healthy = False
    except Exception as e:
        logger.warning(f"Celery health check failed: {e}")
        checks["celery"] = f"error: {type(e).__name__}"
        overall_healthy = False

    status_code = 200 if overall_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if overall_healthy else "unhealthy",
            "service": "labreportai",
            "checks": checks,
        },
    )
