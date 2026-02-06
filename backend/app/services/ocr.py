"""OCR service using Tesseract.

Handles images (direct OCR) and PDFs (convert to images first).
Includes garbage text detection heuristic.

Tesseract is used instead of PaddleOCR for significantly lower memory usage:
- PaddleOCR: ~800MB for model loading
- Tesseract: ~50-100MB per page (loads/unloads)

This makes it suitable for servers with limited RAM (e.g., 1GB).
"""
import logging
import re
from pathlib import Path

import pytesseract
from pdf2image import convert_from_path
from PIL import Image

logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Raised when OCR extraction fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def extract_text_from_image(image_path: str | Path) -> str:
    """Extract text from a single image using Tesseract.

    Args:
        image_path: Path to the image file.

    Returns:
        Extracted text as a string.
    """
    try:
        image = Image.open(image_path)
        # Use English language, assume single block of text
        text = pytesseract.image_to_string(image, lang='eng')
        return text.strip()
    except Exception as e:
        logger.error(f"OCR failed for {image_path}: {e}")
        return ""


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
        # Use lower DPI (150) to reduce memory usage
        # Lab reports are typically clear text, so this is sufficient
        images = convert_from_path(str(pdf_path), dpi=150)
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

        try:
            # Process image directly without saving to temp file
            page_text = pytesseract.image_to_string(image, lang='eng')
            if page_text.strip():
                all_text.append(f"--- Page {i + 1} ---\n{page_text.strip()}")
        except Exception as e:
            logger.error(f"OCR failed for page {i + 1}: {e}")
            continue

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
