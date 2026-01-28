"""LLM-based pre-validation service.

Uses a cheap/fast LLM to determine if OCR text is from a lab report.
"""
import json
import logging
from pathlib import Path
from typing import NamedTuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings
from app.services.llm_provider import get_validation_llm

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "pre_validation.txt"


class ValidationResult(NamedTuple):
    """Result of lab report validation."""

    is_lab_report: bool
    confidence: float
    reason: str


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def load_prompt_template() -> str:
    """Load the pre-validation prompt template."""
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def validate_lab_report(ocr_text: str, max_retries: int = 2) -> ValidationResult:
    """Validate if OCR text is from a lab report using LLM.

    Args:
        ocr_text: The OCR-extracted text to validate.
        max_retries: Number of retries on failure.

    Returns:
        ValidationResult with is_lab_report, confidence, and reason.

    Raises:
        ValidationError: If validation fails after retries.
    """
    settings = get_settings()
    prompt_template = load_prompt_template()

    # Format prompt with OCR text
    prompt = prompt_template.format(ocr_text=ocr_text[:4000])  # Limit text length

    logger.info(f"Validating document with LLM ({settings.llm_validation_model})...")

    llm = get_validation_llm()

    for attempt in range(max_retries + 1):
        try:
            # Call LLM
            response = llm.invoke([HumanMessage(content=prompt)])
            response_text = response.content.strip()

            # Parse JSON response
            result = parse_validation_response(response_text)
            logger.info(
                f"Validation result: is_lab_report={result.is_lab_report}, "
                f"confidence={result.confidence:.2f}, reason={result.reason[:50]}..."
            )
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Attempt {attempt + 1}: Failed to parse LLM response: {e}")
            if attempt == max_retries:
                raise ValidationError(
                    "Failed to validate document: LLM response was not valid JSON."
                )
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: Validation error: {e}")
            if attempt == max_retries:
                raise ValidationError(f"Failed to validate document: {e}")

    # Should not reach here
    raise ValidationError("Validation failed after retries.")


def parse_validation_response(response_text: str) -> ValidationResult:
    """Parse the LLM's JSON response.

    Args:
        response_text: Raw text response from LLM.

    Returns:
        Parsed ValidationResult.
    """
    # Try to extract JSON from response (might have markdown code blocks)
    json_text = response_text

    # Handle markdown code blocks
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0]
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0]

    # Parse JSON
    data = json.loads(json_text.strip())

    return ValidationResult(
        is_lab_report=bool(data.get("is_lab_report", False)),
        confidence=float(data.get("confidence", 0.0)),
        reason=str(data.get("reason", "No reason provided")),
    )


def check_validation_threshold(result: ValidationResult) -> bool:
    """Check if validation result meets the confidence threshold.

    Args:
        result: The validation result.

    Returns:
        True if the document passes validation.
    """
    settings = get_settings()

    if not result.is_lab_report:
        return False

    return result.confidence >= settings.validation_threshold
