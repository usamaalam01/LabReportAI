"""Report analysis Celery task.

Pipeline: OCR → PII scrub → LLM analysis → translate (if Urdu)
         → markdown render → charts → PDF → WhatsApp notification (if WhatsApp source).

Note: Pre-validation (is this a lab report?) is now done during upload, not here.
"""
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import sync_engine
from app.models.report import Report, ReportSource, ReportStatus
from app.services.chart_generator import generate_charts_for_report
from app.services.llm_analyzer import AnalysisError, analyze_lab_report
from app.services.pdf_generator import PDFGenerationError, generate_pdf
from app.services.markdown_renderer import render_analysis_markdown
from app.services.ocr import OCRError, extract_text
from app.services.pii_scrubber import scrub_pii
from app.services.translator import TranslationError, translate_analysis
from app.services.whatsapp_sender import send_whatsapp_message
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="analyze_report", bind=True, max_retries=1)
def analyze_report(self, report_id: str) -> dict:
    """Analyze a lab report.

    Pipeline:
    1. OCR extraction (with garbage text detection)
    2. PII scrubbing
    3. LLM analysis (structured JSON interpretation)
    4. Translation to Urdu (if language == "ur") — non-fatal
    5. Markdown rendering from analysis JSON
    6. Chart generation (Matplotlib bar + gauge)
    7. PDF generation (WeasyPrint, with RTL if Urdu)
    8. WhatsApp notification (if source == WHATSAPP) — non-fatal

    Note: Pre-validation is done during upload, not in this task.
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

            # Step 3: LLM Analysis (with original OCR text to extract patient info)
            # Note: Pre-validation was already done during upload
            logger.info("Step 3: LLM analysis")
            try:
                analysis_result = analyze_lab_report(
                    ocr_text=ocr_text,  # Use original text to extract patient demographics
                    age=report.age,
                    gender=report.gender,
                )
            except AnalysisError as e:
                logger.warning(f"LLM analysis failed: {e.message}")
                report.status = ReportStatus.FAILED
                report.error_message = e.message
                session.commit()
                return {"status": "failed", "message": e.message}

            # Step 4: Translation (if Urdu) — non-fatal
            display_result = analysis_result  # default to English
            if report.language == "ur":
                logger.info("Step 4: Translating to Urdu")
                try:
                    display_result = translate_analysis(analysis_result)
                    logger.info("Translation complete")
                except TranslationError as e:
                    logger.warning(
                        f"Translation failed (non-fatal): {e.message}"
                    )
                    # Fall back to English
            else:
                logger.info("Step 4: Skipping translation (language=en)")

            # Step 5: Render markdown from (translated or English) JSON
            logger.info("Step 5: Rendering markdown")
            markdown = render_analysis_markdown(display_result)

            # Step 6: Generate charts (from ORIGINAL English JSON — numeric values)
            logger.info("Step 6: Generating charts")
            charts = {}
            try:
                charts = generate_charts_for_report(
                    analysis_result, report.job_id
                )
                logger.info(f"Charts generated for {len(charts)} categories")
            except Exception as e:
                logger.warning(f"Chart generation failed (non-fatal): {e}")

            # Step 7: Generate PDF (non-fatal on failure)
            logger.info("Step 7: Generating PDF")
            try:
                pdf_path = generate_pdf(
                    display_result,
                    charts,
                    report.job_id,
                    language=report.language,
                )
                report.result_pdf_path = pdf_path
                logger.info(f"PDF generated: {pdf_path}")
            except PDFGenerationError as e:
                logger.warning(
                    f"PDF generation failed (non-fatal): {e.message}"
                )
            except Exception as e:
                logger.warning(f"PDF generation failed (non-fatal): {e}")

            # Store results (original English JSON always, translated markdown)
            report.status = ReportStatus.COMPLETED
            report.result_json = json.dumps(
                analysis_result, ensure_ascii=False
            )
            report.result_markdown = markdown
            session.commit()

            # Step 8: WhatsApp notification (if WhatsApp source) — non-fatal
            if (
                report.source == ReportSource.WHATSAPP
                and report.whatsapp_number
            ):
                logger.info("Step 8: Sending WhatsApp notification")
                try:
                    summary = display_result.get(
                        "summary", "Analysis complete."
                    )
                    msg = (
                        f"Lab Report Analysis Results:\n\n"
                        f"{summary[:1400]}"
                    )
                    send_whatsapp_message(report.whatsapp_number, msg)
                    logger.info("WhatsApp notification sent")
                except Exception as e:
                    logger.warning(
                        f"WhatsApp notification failed (non-fatal): {e}"
                    )

            logger.info(f"Analysis completed for report_id={report_id}")
            return {"status": "completed", "report_id": report_id}

        except Exception as e:
            logger.exception(f"Analysis failed for report_id={report_id}")
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            session.commit()
            raise self.retry(exc=e, countdown=5)
