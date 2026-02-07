import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.middleware import RateLimitExceeded, check_rate_limit
from app.config import get_settings
from app.db.session import get_db
from app.models.report import Report, ReportStatus
from app.schemas.report import AnalyzeReportResponse, ErrorResponse, ReportStatusResponse
from app.services.file_validator import FileValidationError, validate_file
from app.services.ocr import OCRError, extract_text
from app.services.llm_validator import ValidationError, check_validation_threshold, validate_lab_report
from app.tasks.analyze import analyze_report
from app.utils.recaptcha import RecaptchaError, verify_recaptcha

# Thread pool for running sync OCR/validation in async context
_executor = ThreadPoolExecutor(max_workers=2)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze-report",
    response_model=AnalyzeReportResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def submit_report(
    request: Request,
    file: UploadFile = File(...),
    age: int | None = Form(None),
    gender: str | None = Form(None),
    language: str = Form("en"),
    captcha_token: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Submit a lab report for analysis. Returns a job_id for polling."""
    settings = get_settings()

    # Rate limit check
    try:
        await check_rate_limit(request)
    except RateLimitExceeded as e:
        return JSONResponse(
            status_code=429,
            content={"status": "error", "code": 429, "message": e.message},
            headers={"Retry-After": str(e.retry_after)},
        )

    # reCAPTCHA verification (skipped when not configured)
    try:
        await verify_recaptcha(captcha_token or "")
    except RecaptchaError as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": e.message},
        )

    # Validate file
    try:
        await validate_file(file)
    except FileValidationError as e:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": e.message},
        )

    # Validate language
    if language not in ("en", "ur"):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": "Unsupported language. Allowed: en, ur."},
        )

    # Save file to storage
    job_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".pdf"
    upload_dir = Path(settings.uploads_path)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_path = upload_dir / f"{job_id}{file_ext}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text with OCR (runs in thread pool)
    loop = asyncio.get_event_loop()
    try:
        ocr_text = await loop.run_in_executor(_executor, extract_text, str(file_path))
    except OCRError as e:
        # Clean up file on error
        file_path.unlink(missing_ok=True)
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": e.message},
        )

    if not ocr_text or len(ocr_text.strip()) < 50:
        file_path.unlink(missing_ok=True)
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "code": 400,
                "message": "Could not extract readable text from the document. Please ensure the image is clear and contains text.",
            },
        )

    # Validate that this is a lab report (runs in thread pool)
    try:
        validation_result = await loop.run_in_executor(_executor, validate_lab_report, ocr_text)

        if not check_validation_threshold(validation_result):
            file_path.unlink(missing_ok=True)
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "code": 400,
                    "message": f"This does not appear to be a lab report. {validation_result.reason}",
                },
            )
    except ValidationError as e:
        # If validation fails due to LLM error, let it proceed (fail open)
        logger.warning(f"Validation error (proceeding anyway): {e.message}")

    # Create DB record
    report = Report(
        job_id=job_id,
        status=ReportStatus.PENDING,
        file_path=str(file_path),
        file_type=file.content_type or "application/octet-stream",
        age=age,
        gender=gender,
        language=language,
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.retention_period),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    report_id = str(report.id)

    # Dispatch Celery task
    analyze_report.delay(report_id)

    logger.info(f"Report submitted: job_id={job_id}, file={file.filename}")

    return AnalyzeReportResponse(job_id=job_id)


@router.get(
    "/status/{job_id}",
    response_model=ReportStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_report_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Poll for report status and results."""
    result = await db.execute(
        select(Report).where(Report.job_id == job_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": 404, "message": "Report not found."},
        )

    pdf_url = None
    if report.result_pdf_path and os.path.exists(report.result_pdf_path):
        pdf_url = f"/v1/download/{job_id}"

    return ReportStatusResponse(
        job_id=report.job_id,
        status=report.status.value,
        result_markdown=report.result_markdown,
        result_pdf_url=pdf_url,
        error_message=report.error_message,
        created_at=report.created_at,
    )


@router.get(
    "/download/{job_id}",
    responses={404: {"model": ErrorResponse}},
)
async def download_report(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download the generated PDF report."""
    result = await db.execute(
        select(Report).where(Report.job_id == job_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": 404, "message": "Report not found."},
        )

    if not report.result_pdf_path or not os.path.exists(report.result_pdf_path):
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": 404, "message": "PDF not yet generated."},
        )

    return FileResponse(
        path=report.result_pdf_path,
        media_type="application/pdf",
        filename=f"report_{job_id}.pdf",
    )
