import enum
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportSource(str, enum.Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, values_callable=lambda e: [x.value for x in e]),
        default=ReportStatus.PENDING,
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)

    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)

    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[ReportSource] = mapped_column(
        Enum(ReportSource, values_callable=lambda e: [x.value for x in e]),
        default=ReportSource.WEB,
        nullable=False,
    )
    whatsapp_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=48),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Report(job_id={self.job_id}, status={self.status})>"
