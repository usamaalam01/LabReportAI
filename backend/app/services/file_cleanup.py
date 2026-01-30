"""Expired report cleanup — hard deletes files and database records."""
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import sync_engine
from app.models.report import Report

logger = logging.getLogger(__name__)


def cleanup_expired_reports() -> int:
    """Delete expired reports: uploaded files, output dirs, and DB records.

    Returns number of records cleaned up.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    cleaned = 0

    with Session(sync_engine) as session:
        expired = (
            session.execute(
                select(Report).where(Report.expires_at <= now)
            )
            .scalars()
            .all()
        )

        for report in expired:
            # Delete uploaded file
            if report.file_path:
                file_path = Path(report.file_path)
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.debug(f"Deleted upload: {file_path}")
                    except OSError as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")

            # Delete output directory (charts + PDF)
            if report.job_id:
                output_dir = Path(settings.outputs_path) / report.job_id
                if output_dir.exists():
                    try:
                        shutil.rmtree(output_dir)
                        logger.debug(f"Deleted outputs: {output_dir}")
                    except OSError as e:
                        logger.warning(f"Failed to delete {output_dir}: {e}")

            # Delete DB record
            session.delete(report)
            cleaned += 1

        if cleaned:
            session.commit()

    return cleaned
