import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import sync_engine
from app.models.report import Report, ReportStatus
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

PLACEHOLDER_MARKDOWN = """# Lab Report Analysis

## Patient Information
- **Age:** {age}
- **Gender:** {gender}
- **Report Date:** N/A

## Summary
This is a placeholder analysis. The full LLM analysis pipeline will be implemented in Phase 3.

## Category-wise Results
| Test | Value | Unit | Reference Range | Status |
|------|-------|------|----------------|--------|
| Hemoglobin | 14.5 | g/dL | 13.0 - 17.0 | Normal |
| WBC | 7,500 | /uL | 4,500 - 11,000 | Normal |

## Abnormal Values Analysis
No abnormal values detected in placeholder data.

## Clinical Associations
Full clinical associations will be available once LLM analysis is integrated.

## Lifestyle Tips
- Maintain a balanced diet rich in fruits and vegetables.
- Stay hydrated and exercise regularly.

## Disclaimer
> This report provides educational insights and clinical associations only. It is not a diagnosis or treatment recommendation. Please consult a qualified physician.
"""


@celery_app.task(name="analyze_report", bind=True, max_retries=1)
def analyze_report(self, report_id: str) -> dict:
    """Stub Celery task: simulates report analysis.

    Phase 1: sleep 3s, set placeholder markdown.
    Phase 2+: OCR → PII scrub → pre-validate → LLM analysis → charts → PDF.
    """
    logger.info(f"Starting analysis for report_id={report_id}")

    with Session(sync_engine) as session:
        report = session.execute(
            select(Report).where(Report.id == report_id)
        ).scalar_one_or_none()

        if not report:
            logger.error(f"Report not found: {report_id}")
            return {"status": "error", "message": "Report not found"}

        # Update status to processing
        report.status = ReportStatus.PROCESSING
        session.commit()

        try:
            # Phase 1: stub — sleep to simulate processing
            time.sleep(3)

            # Generate placeholder markdown
            age_str = str(report.age) if report.age else "Not provided"
            gender_str = report.gender if report.gender else "Not provided"
            markdown = PLACEHOLDER_MARKDOWN.format(age=age_str, gender=gender_str)

            # Update report with results
            report.status = ReportStatus.COMPLETED
            report.result_markdown = markdown
            session.commit()

            logger.info(f"Analysis completed for report_id={report_id}")
            return {"status": "completed", "report_id": report_id}

        except Exception as e:
            logger.exception(f"Analysis failed for report_id={report_id}")
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            session.commit()
            raise self.retry(exc=e, countdown=5)
