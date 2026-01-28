import logging
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


class FileValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def validate_file(file: UploadFile) -> None:
    """Validate uploaded file: type, size, and page count."""
    settings = get_settings()

    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(
            f"Unsupported file type: {file.content_type}. "
            f"Allowed: PDF, JPEG, PNG."
        )

    # Check file extension
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise FileValidationError(
                f"Unsupported file extension: {ext}. "
                f"Allowed: .pdf, .jpg, .jpeg, .png."
            )

    # Check file size
    content = await file.read()
    await file.seek(0)

    if len(content) > settings.max_file_size:
        max_mb = settings.max_file_size / (1024 * 1024)
        raise FileValidationError(
            f"File too large ({len(content) / (1024 * 1024):.1f} MB). "
            f"Maximum allowed: {max_mb:.0f} MB."
        )

    # Check page count for PDFs
    if file.content_type == "application/pdf":
        try:
            from PyPDF2 import PdfReader
            import io

            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
            if page_count > settings.max_pages:
                raise FileValidationError(
                    f"PDF has {page_count} pages. "
                    f"Maximum allowed: {settings.max_pages} pages."
                )
        except FileValidationError:
            raise
        except Exception as e:
            logger.warning(f"Could not read PDF page count: {e}")
            raise FileValidationError("Could not read the PDF file. It may be corrupted.")

    logger.info(
        f"File validated: {file.filename}, type={file.content_type}, "
        f"size={len(content)} bytes"
    )
