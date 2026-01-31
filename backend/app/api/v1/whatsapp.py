"""WhatsApp webhook endpoint for Twilio integration.

Receives incoming WhatsApp messages, processes lab report images/PDFs,
and dispatches analysis tasks.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Form, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import sync_engine
from app.models.report import Report, ReportSource, ReportStatus
from app.services.whatsapp_sender import is_whatsapp_enabled, send_whatsapp_message
from app.tasks.analyze import analyze_report
from app.utils.pii_sanitizer import sanitize_phone_number

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp")

WELCOME_MSG = (
    "Welcome to Lab Report AI!\n\n"
    "Send a photo or PDF of your lab report and I'll analyze it for you.\n\n"
    "آپ کی لیب رپورٹ کی تصویر یا PDF بھیجیں، میں اسے تجزیہ کروں گا۔"
)

PROCESSING_MSG = (
    "Your lab report is being analyzed. You'll receive the results shortly.\n\n"
    "آپ کی لیب رپورٹ کا تجزیہ ہو رہا ہے۔ نتائج جلد بھیجے جائیں گے۔"
)

UNSUPPORTED_MSG = (
    "Please send a photo (JPEG/PNG) or PDF of your lab report.\n\n"
    "براہ کرم اپنی لیب رپورٹ کی تصویر (JPEG/PNG) یا PDF بھیجیں۔"
)

ERROR_MSG = (
    "An error occurred while processing your report. Please try again.\n\n"
    "رپورٹ پر عمل کرنے میں خرابی ہوئی۔ براہ کرم دوبارہ کوشش کریں۔"
)

ALLOWED_MEDIA_TYPES = {
    "image/jpeg",
    "image/png",
    "application/pdf",
}

EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}


@router.post("/webhook")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: str | None = Form(None),
    MediaContentType0: str | None = Form(None),
):
    """Twilio WhatsApp webhook — receives incoming messages.

    Handles two cases:
    1. Media message (image/PDF): downloads file, creates report, dispatches analysis
    2. Text message: sends welcome/instruction message
    """
    if not is_whatsapp_enabled():
        return Response(content="", media_type="text/xml")

    # Strip "whatsapp:" prefix from phone number
    phone = From.replace("whatsapp:", "")
    logger.info(f"WhatsApp message from {sanitize_phone_number(phone)}: NumMedia={NumMedia}")

    if NumMedia > 0 and MediaUrl0 and MediaContentType0:
        await _handle_media_message(phone, MediaUrl0, MediaContentType0)
    else:
        send_whatsapp_message(phone, WELCOME_MSG)

    # Return empty TwiML (we send messages via REST API, not TwiML)
    return Response(content="", media_type="text/xml")


async def _handle_media_message(
    phone: str, media_url: str, content_type: str
) -> None:
    """Download media from Twilio, create report, and dispatch analysis."""
    if content_type not in ALLOWED_MEDIA_TYPES:
        send_whatsapp_message(phone, UNSUPPORTED_MSG)
        return

    try:
        settings = get_settings()

        # Download media from Twilio (requires auth)
        async with httpx.AsyncClient(
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=30.0,
        ) as client:
            resp = await client.get(media_url)
            resp.raise_for_status()
            file_content = resp.content

        # Save file
        ext = EXT_MAP.get(content_type, ".jpg")
        job_id = str(uuid.uuid4())
        upload_dir = Path(settings.uploads_path)
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / f"{job_id}{ext}"
        file_path.write_bytes(file_content)

        logger.info(
            f"WhatsApp media saved: {file_path} ({len(file_content)} bytes)"
        )

        # Create DB record
        with Session(sync_engine) as session:
            report = Report(
                job_id=job_id,
                status=ReportStatus.PENDING,
                file_path=str(file_path),
                file_type=content_type,
                language="ur",  # Default Urdu for WhatsApp
                source=ReportSource.WHATSAPP,
                whatsapp_number=phone,
                expires_at=datetime.now(timezone.utc)
                + timedelta(hours=settings.retention_period),
            )
            session.add(report)
            session.commit()
            report_id = str(report.id)

        # Dispatch analysis task
        analyze_report.delay(report_id)
        send_whatsapp_message(phone, PROCESSING_MSG)

        logger.info(
            f"WhatsApp report submitted: job_id={job_id}, phone={sanitize_phone_number(phone)}"
        )

    except Exception as e:
        logger.exception(f"WhatsApp media processing error: {e}")
        send_whatsapp_message(phone, ERROR_MSG)
