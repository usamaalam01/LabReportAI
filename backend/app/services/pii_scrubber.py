"""PII (Personally Identifiable Information) scrubber.

Removes/redacts personal information from OCR text before sending to LLM.
Uses regex-based pattern matching for 7 PII categories.
"""
import logging
import re

logger = logging.getLogger(__name__)


# PII patterns and their replacements
PII_PATTERNS = [
    # Patient Name - Common lab report patterns
    # "Patient Name: John Doe" or "Name: John Doe"
    (
        r"(?i)(patient\s*name|name)\s*[:]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"\1: [REDACTED]",
    ),
    # "Mr./Mrs./Ms./Dr. First Last"
    (
        r"(?i)\b(Mr\.?|Mrs\.?|Ms\.?|Miss|Dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b",
        r"[REDACTED]",
    ),

    # Patient ID / MRN (Medical Record Number)
    (
        r"(?i)(patient\s*id|mrn|medical\s*record\s*(?:number|no\.?)|uhid|hospital\s*id)\s*[:]\s*[\w-]+",
        r"\1: [ID_REDACTED]",
    ),
    # Standalone ID patterns like "MRN: 12345" or "ID: ABC123"
    (
        r"(?i)\b(id|mrn)\s*[:]\s*[A-Z0-9-]{4,20}\b",
        r"\1: [ID_REDACTED]",
    ),

    # Phone Numbers
    # International format: +92-300-1234567, +1 (555) 123-4567
    (
        r"\+?\d{1,3}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}",
        "[PHONE_REDACTED]",
    ),
    # Pakistani mobile: 03XX-XXXXXXX
    (
        r"\b0[3][0-9]{2}[-.\s]?[0-9]{7}\b",
        "[PHONE_REDACTED]",
    ),

    # Addresses
    # House/Street patterns
    (
        r"(?i)(house\s*(?:no\.?|#)?|street|road|lane|block|sector|phase)\s*[:.]?\s*[\w\s,.-]{5,50}",
        "[ADDRESS_REDACTED]",
    ),
    # City, Country patterns after comma
    (
        r"(?i),\s*(karachi|lahore|islamabad|rawalpindi|faisalabad|multan|peshawar|quetta|hyderabad|sialkot)(?:\s*,\s*pakistan)?",
        ", [CITY_REDACTED]",
    ),

    # Date of Birth
    (
        r"(?i)(date\s*of\s*birth|dob|d\.o\.b\.?|birth\s*date)\s*[:]\s*[\d/.-]+",
        r"\1: [DOB_REDACTED]",
    ),
    # DD/MM/YYYY or MM/DD/YYYY or YYYY-MM-DD near age/birth context
    (
        r"(?i)(?:born|dob)\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})",
        r"born: [DOB_REDACTED]",
    ),

    # Doctor Name
    (
        r"(?i)(referred\s*by|doctor|physician|consultant|dr\.?)\s*[:.]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"\1: [DOCTOR_REDACTED]",
    ),
    # "Dr. Name" standalone
    (
        r"(?i)\bDr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b",
        "[DOCTOR_REDACTED]",
    ),

    # Hospital / Lab Name
    (
        r"(?i)(hospital|laboratory|lab|clinic|medical\s*center|diagnostic\s*center|healthcare)\s*[:.]?\s*([A-Z][A-Za-z\s&]+(?:Hospital|Lab|Clinic|Center|Healthcare|Diagnostics)?)",
        r"\1: [LAB_REDACTED]",
    ),
    # Common lab name patterns
    (
        r"(?i)\b(Chughtai|Shaukat\s*Khanum|Aga\s*Khan|Excel|Essa|Ziauddin|Liaquat|Indus|OMI|Dow)\s+(?:Lab|Hospital|Diagnostic|Medical|Healthcare)?\w*\b",
        "[LAB_REDACTED]",
    ),

    # Email addresses (bonus)
    (
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "[EMAIL_REDACTED]",
    ),

    # CNIC (Pakistani National ID)
    (
        r"\b\d{5}-\d{7}-\d{1}\b",
        "[CNIC_REDACTED]",
    ),
]


def scrub_pii(text: str) -> str:
    """Remove PII from OCR text using regex patterns.

    Args:
        text: Raw OCR text with potential PII.

    Returns:
        Scrubbed text with PII replaced by redaction markers.
    """
    if not text:
        return text

    scrubbed = text
    redaction_count = 0

    for pattern, replacement in PII_PATTERNS:
        matches = re.findall(pattern, scrubbed)
        if matches:
            redaction_count += len(matches)
            scrubbed = re.sub(pattern, replacement, scrubbed)

    if redaction_count > 0:
        logger.info(f"Scrubbed {redaction_count} PII instances from text")

    return scrubbed


def get_pii_summary(original: str, scrubbed: str) -> dict:
    """Get a summary of what PII was redacted.

    Args:
        original: Original text before scrubbing.
        scrubbed: Text after scrubbing.

    Returns:
        Dict with counts of each redaction type.
    """
    redaction_markers = [
        "[REDACTED]",
        "[ID_REDACTED]",
        "[PHONE_REDACTED]",
        "[ADDRESS_REDACTED]",
        "[CITY_REDACTED]",
        "[DOB_REDACTED]",
        "[DOCTOR_REDACTED]",
        "[LAB_REDACTED]",
        "[EMAIL_REDACTED]",
        "[CNIC_REDACTED]",
    ]

    summary = {}
    for marker in redaction_markers:
        count = scrubbed.count(marker)
        if count > 0:
            key = marker.strip("[]").lower()
            summary[key] = count

    return summary
