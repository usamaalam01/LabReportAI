"""
PII (Personally Identifiable Information) sanitization utility.

Provides functions to detect and redact sensitive data from logs
to comply with privacy requirements.
"""
import re
from typing import Any, Dict


# Regex patterns for PII detection
PHONE_PATTERN = re.compile(
    r"""
    (?:
        \+?\d{1,3}[-.\s]?       # Country code
        (?:\(\d{1,4}\)|\d{1,4}) # Area code
        [-.\s]?\d{1,4}          # First part
        [-.\s]?\d{1,4}          # Second part
        [-.\s]?\d{1,9}          # Last part
    )
    """,
    re.VERBOSE
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
)

# Common Pakistani/Urdu name patterns (simplified)
NAME_INDICATORS = [
    "patient name", "name:", "patient:", "mr.", "mrs.", "ms.", "dr.",
    "نام", "مریض", "کا نام"  # Urdu: name, patient
]

# Medical value patterns (numbers with units that might be sensitive)
MEDICAL_VALUE_PATTERN = re.compile(
    r"\b\d+\.?\d*\s*(mg/dl|mmol/l|g/dl|%|cells/μl|iu/ml|pg/ml|ng/ml|μg/dl)\b",
    re.IGNORECASE
)


def sanitize_phone_number(text: str) -> str:
    """
    Redact phone numbers from text.

    Args:
        text: Input text that may contain phone numbers

    Returns:
        Text with phone numbers replaced with [PHONE_REDACTED]
    """
    return PHONE_PATTERN.sub("[PHONE_REDACTED]", text)


def sanitize_email(text: str) -> str:
    """
    Redact email addresses from text.

    Args:
        text: Input text that may contain emails

    Returns:
        Text with emails replaced with [EMAIL_REDACTED]
    """
    return EMAIL_PATTERN.sub("[EMAIL_REDACTED]", text)


def sanitize_medical_values(text: str) -> str:
    """
    Redact medical test values from text.

    Args:
        text: Input text that may contain medical values

    Returns:
        Text with medical values replaced with [VALUE_REDACTED]
    """
    return MEDICAL_VALUE_PATTERN.sub("[VALUE_REDACTED]", text)


def sanitize_patient_name(text: str, patient_name: str = None) -> str:
    """
    Redact patient name if known.

    Args:
        text: Input text
        patient_name: Known patient name to redact (optional)

    Returns:
        Text with patient name replaced with [NAME_REDACTED]
    """
    if patient_name and len(patient_name) > 2:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(patient_name), re.IGNORECASE)
        text = pattern.sub("[NAME_REDACTED]", text)

    return text


def sanitize_text(text: str, patient_name: str = None) -> str:
    """
    Apply all PII sanitization rules to text.

    This is the main function to use for sanitizing log messages.

    Args:
        text: Input text to sanitize
        patient_name: Optional patient name to redact

    Returns:
        Sanitized text with all PII redacted

    Example:
        >>> sanitize_text("Patient John Doe, phone +92-300-1234567, glucose 120 mg/dl")
        "Patient [NAME_REDACTED], phone [PHONE_REDACTED], glucose [VALUE_REDACTED]"
    """
    if not isinstance(text, str):
        return text

    # Apply all sanitization rules
    text = sanitize_phone_number(text)
    text = sanitize_email(text)
    text = sanitize_medical_values(text)

    if patient_name:
        text = sanitize_patient_name(text, patient_name)

    return text


def sanitize_dict(data: Dict[str, Any], patient_name: str = None) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.

    Useful for sanitizing structured data like JSON payloads before logging.

    Args:
        data: Dictionary to sanitize
        patient_name: Optional patient name to redact

    Returns:
        Dictionary with all string values sanitized
    """
    if not isinstance(data, dict):
        return data

    sanitized = {}

    for key, value in data.items():
        # Skip certain safe keys that don't contain PII
        safe_keys = {
            "job_id", "status", "file_type", "language",
            "processing_step", "error_code", "timestamp"
        }

        if key in safe_keys:
            sanitized[key] = value
        elif isinstance(value, str):
            sanitized[key] = sanitize_text(value, patient_name)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, patient_name)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item, patient_name) if isinstance(item, dict)
                else sanitize_text(item, patient_name) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            # Numbers, booleans, None, etc. - pass through
            sanitized[key] = value

    return sanitized


def safe_log_message(message: str, **kwargs) -> str:
    """
    Create a safe log message by sanitizing both the message and kwargs.

    Args:
        message: Log message template
        **kwargs: Additional context to include in log (will be sanitized)

    Returns:
        Sanitized log message string

    Example:
        >>> safe_log_message("Processing report for {patient}", patient="John Doe")
        "Processing report for [NAME_REDACTED]"
    """
    # Extract patient name if provided for context-aware sanitization
    patient_name = kwargs.get("patient_name") or kwargs.get("patient")

    # Sanitize the message
    message = sanitize_text(message, patient_name)

    # Sanitize all kwargs
    sanitized_kwargs = sanitize_dict(kwargs, patient_name)

    # Format message with sanitized kwargs
    try:
        return message.format(**sanitized_kwargs)
    except (KeyError, ValueError):
        # If formatting fails, return sanitized message as-is
        return message


# Convenience function for common logging pattern
def sanitize_for_log(obj: Any, patient_name: str = None) -> Any:
    """
    Sanitize any object for safe logging.

    Args:
        obj: Object to sanitize (str, dict, list, etc.)
        patient_name: Optional patient name for context-aware redaction

    Returns:
        Sanitized version of the object
    """
    if isinstance(obj, str):
        return sanitize_text(obj, patient_name)
    elif isinstance(obj, dict):
        return sanitize_dict(obj, patient_name)
    elif isinstance(obj, list):
        return [sanitize_for_log(item, patient_name) for item in obj]
    else:
        return obj
