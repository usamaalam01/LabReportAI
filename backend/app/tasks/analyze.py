"""Report analysis Celery task.

Phase 2: OCR → PII scrub → pre-validate → store scrubbed text.
Phase 3+: Full LLM analysis → charts → PDF.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import sync_engine
from app.models.report import Report, ReportStatus
from app.services.llm_validator import (
    ValidationError,
    check_validation_threshold,
    validate_lab_report,
)
from app.services.ocr import OCRError, extract_text
from app.services.pii_scrubber import scrub_pii
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

PLACEHOLDER_MARKDOWN = """# Lab Report Analysis

## Patient Information
- **Age:** {age}
- **Gender:** {gender}
- **Report Date:** N/A

## Summary
OCR extraction and pre-validation completed successfully. Full LLM analysis will be implemented in Phase 3.

## Extracted Text Preview
The following text was extracted from your lab report (PII redacted):

```
{ocr_preview}
```

## Category-wise Results
Full analysis with categorized results will be available in Phase 3.

## Disclaimer
> This report provides educational insights and clinical associations only. It is not a diagnosis or treatment recommendation. Please consult a qualified physician.
"""


@celery_app.task(name="analyze_report", bind=True, max_retries=1)
def analyze_report(self, report_id: str) -> dict:
    """Analyze a lab report.

    Phase 2 pipeline:
    1. OCR extraction (with garbage text detection)
    2. PII scrubbing
    3. Pre-validation (LLM checks if it's a lab report)
    4. Store scrubbed text in DB
    5. Generate placeholder markdown

    Phase 3+ will add:
    - Full LLM analysis
    - Chart generation
    - PDF generation
    """
    logger.info(f"Starting analysis for report_id={report_id}")
    settings = get_settings()

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
            # Step 1: OCR extraction
            logger.info(f"Step 1: OCR extraction from {report.file_path}")
            try:
                ocr_text = extract_text(report.file_path)
            except OCRError as e:
                logger.warning(f"OCR failed: {e.message}")
                report.status = ReportStatus.FAILED
                report.error_message = e.message
                session.commit()
                return {"status": "failed", "message": e.message}

            logger.info(f"OCR extracted {len(ocr_text)} characters")

            # Step 2: PII scrubbing
            logger.info("Step 2: PII scrubbing")
            scrubbed_text = scrub_pii(ocr_text)
            report.ocr_text = scrubbed_text

            # Step 3: Pre-validation with LLM
            logger.info("Step 3: Pre-validation with LLM")
            try:
                validation_result = validate_lab_report(scrubbed_text)

                if not check_validation_threshold(validation_result):
                    error_msg = (
                        f"This does not appear to be a lab report. "
                        f"Reason: {validation_result.reason}"
                    )
                    logger.warning(f"Pre-validation failed: {error_msg}")
                    report.status = ReportStatus.FAILED
                    report.error_message = error_msg
                    session.commit()
                    return {"status": "failed", "message": error_msg}

                logger.info(
                    f"Pre-validation passed: confidence={validation_result.confidence:.2f}"
                )

            except ValidationError as e:
                logger.warning(f"Validation error: {e.message}")
                report.status = ReportStatus.FAILED
                report.error_message = e.message
                session.commit()
                return {"status": "failed", "message": e.message}

            # Step 4: Generate placeholder markdown (Phase 3 will do full analysis)
            logger.info("Step 4: Generating placeholder markdown")
            age_str = str(report.age) if report.age else "Not provided"
            gender_str = report.gender if report.gender else "Not provided"
            ocr_preview = scrubbed_text[:500] + "..." if len(scrubbed_text) > 500 else scrubbed_text

            markdown = PLACEHOLDER_MARKDOWN.format(
                age=age_str,
                gender=gender_str,
                ocr_preview=ocr_preview,
            )

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
