"""Celery Beat periodic task: clean up expired reports."""
import logging

from app.services.file_cleanup import cleanup_expired_reports
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="cleanup_expired_reports")
def cleanup_expired_reports_task() -> dict:
    """Periodic task: clean up expired reports (files + DB records)."""
    logger.info("Starting expired report cleanup...")
    cleaned = cleanup_expired_reports()
    logger.info(f"Cleanup complete: {cleaned} expired reports removed.")
    return {"cleaned": cleaned}
