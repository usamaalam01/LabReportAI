import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.report import Report, ReportStatus
from app.schemas.report import AnalyzeReportResponse, ErrorResponse, ReportStatusResponse
from app.services.file_validator import FileValidationError, validate_file
from app.tasks.analyze import analyze_report

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
    db: AsyncSession = Depends(get_db),
):
    """Submit a lab report for analysis. Returns a job_id for polling."""
    settings = get_settings()

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
    await db.flush()

    report_id = report.id

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
