"""OCR service using PaddleOCR.

Handles images (direct OCR) and PDFs (convert to images first).
Includes garbage text detection heuristic.
"""
import logging
import re
from pathlib import Path

from paddleocr import PaddleOCR
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)

# Singleton PaddleOCR instance (expensive to initialize)
_ocr_instance: PaddleOCR | None = None


def get_ocr() -> PaddleOCR:
    """Get or create the PaddleOCR instance."""
    global _ocr_instance
    if _ocr_instance is None:
        logger.info("Initializing PaddleOCR...")
        _ocr_instance = PaddleOCR(
            use_angle_cls=True,  # Detect rotated text
            lang="en",
            use_gpu=False,  # CPU-only for compatibility
            show_log=False,
        )
        logger.info("PaddleOCR initialized")
    return _ocr_instance


class OCRError(Exception):
    """Raised when OCR extraction fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def extract_text_from_image(image_path: str | Path) -> str:
    """Extract text from a single image using PaddleOCR.

    Args:
        image_path: Path to the image file.

    Returns:
        Extracted text as a string.
    """
    ocr = get_ocr()
    result = ocr.ocr(str(image_path), cls=True)

    if not result or not result[0]:
        return ""

    # Extract text from OCR result
    lines = []
    for line in result[0]:
        if line and len(line) >= 2:
            text = line[1][0]  # (text, confidence)
            lines.append(text)

    return "\n".join(lines)


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """Extract text from a PDF by converting to images and running OCR.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Extracted text as a string (all pages combined).
    """
    logger.info(f"Converting PDF to images: {pdf_path}")

    # Convert PDF pages to images
    try:
        images = convert_from_path(str(pdf_path), dpi=200)
    except Exception as e:
        logger.error(f"Failed to convert PDF: {e}")
        raise OCRError(
            "Text extraction failed - unable to read PDF. "
            "The file may be corrupted or password-protected."
        )

    logger.info(f"PDF has {len(images)} pages")

    # OCR each page
    all_text = []
    for i, image in enumerate(images):
        logger.info(f"OCR processing page {i + 1}/{len(images)}")

        # Save temp image for PaddleOCR
        temp_path = Path(f"/tmp/ocr_page_{i}.png")
        image.save(temp_path, "PNG")

        try:
            page_text = extract_text_from_image(temp_path)
            if page_text:
                all_text.append(f"--- Page {i + 1} ---\n{page_text}")
        finally:
            temp_path.unlink(missing_ok=True)

    return "\n\n".join(all_text)


def extract_text(file_path: str | Path) -> str:
    """Extract text from an image or PDF file.

    Args:
        file_path: Path to the file.

    Returns:
        Extracted text.

    Raises:
        OCRError: If extraction fails or produces garbage text.
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise OCRError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        text = extract_text_from_pdf(file_path)
    elif suffix in (".jpg", ".jpeg", ".png"):
        text = extract_text_from_image(file_path)
    else:
        raise OCRError(f"Unsupported file type: {suffix}")

    # Check for garbage text
    if is_garbage_text(text):
        raise OCRError(
            "The document appears to be blurred or unreadable. "
            "Please upload a clearer image."
        )

    logger.info(f"OCR extracted {len(text)} characters from {file_path.name}")
    return text


def is_garbage_text(text: str, min_length: int = 50, min_word_ratio: float = 0.3) -> bool:
    """Detect if OCR output is garbage (blurred/unreadable image).

    Heuristics:
    1. Very short text is suspicious
    2. Low ratio of recognizable words
    3. High ratio of special characters
    4. Very few numeric characters (lab reports have lots of numbers)

    Args:
        text: OCR extracted text.
        min_length: Minimum character length to be valid.
        min_word_ratio: Minimum ratio of alphanumeric characters.

    Returns:
        True if text appears to be garbage.
    """
    if not text or len(text.strip()) < min_length:
        return True

    # Count alphanumeric vs total characters
    alnum_count = sum(1 for c in text if c.isalnum())
    total_count = len(text.replace(" ", "").replace("\n", ""))

    if total_count == 0:
        return True

    alnum_ratio = alnum_count / total_count
    if alnum_ratio < min_word_ratio:
        return True

    # Check for presence of numbers (lab reports have many)
    digit_count = sum(1 for c in text if c.isdigit())
    digit_ratio = digit_count / total_count if total_count > 0 else 0

    # Lab reports typically have >5% digits (values, ranges, dates)
    if digit_ratio < 0.03:
        logger.warning(f"Low digit ratio: {digit_ratio:.2%}")
        # Don't fail on this alone, just log

    # Check for common garbage patterns
    garbage_patterns = [
        r"[^\w\s.,;:!?()-]{5,}",  # 5+ consecutive special chars
        r"([^0-9])\1{4,}",  # 5+ repeated non-digit characters (allow 00000, 11111 in numbers)
    ]
    for pattern in garbage_patterns:
        if re.search(pattern, text):
            return True

    return False
