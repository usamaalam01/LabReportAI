"""Report analysis Celery task.

Pipeline: OCR → PII scrub → pre-validate → LLM analysis → markdown render.
"""
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import sync_engine
from app.models.report import Report, ReportStatus
from app.services.llm_analyzer import AnalysisError, analyze_lab_report
from app.services.llm_validator import (
    ValidationError,
    check_validation_threshold,
    validate_lab_report,
)
from app.services.markdown_renderer import render_analysis_markdown
from app.services.ocr import OCRError, extract_text
from app.services.pii_scrubber import scrub_pii
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="analyze_report", bind=True, max_retries=1)
def analyze_report(self, report_id: str) -> dict:
    """Analyze a lab report.

    Pipeline:
    1. OCR extraction (with garbage text detection)
    2. PII scrubbing
    3. Pre-validation (LLM checks if it's a lab report)
    4. LLM analysis (structured JSON interpretation)
    5. Markdown rendering from analysis JSON
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

            # Step 4: LLM Analysis
            logger.info("Step 4: LLM analysis")
            try:
                analysis_result = analyze_lab_report(
                    ocr_text=scrubbed_text,
                    age=report.age,
                    gender=report.gender,
                )
            except AnalysisError as e:
                logger.warning(f"LLM analysis failed: {e.message}")
                report.status = ReportStatus.FAILED
                report.error_message = e.message
                session.commit()
                return {"status": "failed", "message": e.message}

            # Step 5: Render markdown from analysis JSON
            logger.info("Step 5: Rendering markdown")
            markdown = render_analysis_markdown(analysis_result)

            # Store both structured JSON and rendered markdown
            report.status = ReportStatus.COMPLETED
            report.result_json = json.dumps(analysis_result, ensure_ascii=False)
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
