from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeReportResponse(BaseModel):
    job_id: str
    status: str = "pending"
    message: str = "Report submitted for analysis."


class ReportStatusResponse(BaseModel):
    job_id: str
    status: str
    result_markdown: str | None = None
    result_pdf_url: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None


class ErrorResponse(BaseModel):
    status: str = "error"
    code: int
    message: str
