"""LLM-based lab report analysis service.

Calls the analysis LLM to interpret lab report OCR text and return
structured JSON with test results, interpretations, and recommendations.
"""
import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.services.llm_provider import get_analysis_llm

logger = logging.getLogger(__name__)

# Load prompt template
PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "analysis.txt"


class AnalysisError(Exception):
    """Raised when LLM analysis fails after retries."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def load_prompt_template() -> str:
    """Load the analysis prompt template."""
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt file not found: {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


def analyze_lab_report(
    ocr_text: str,
    age: int | None = None,
    gender: str | None = None,
    max_retries: int = 2,
) -> dict:
    """Analyze lab report text using the LLM.

    Args:
        ocr_text: Original OCR text from the lab report (includes patient information).
        age: Patient age from form input (optional, used as fallback).
        gender: Patient gender from form input (optional, used as fallback).
        max_retries: Number of retry attempts on failure.

    Returns:
        Parsed analysis dict matching the analysis.txt JSON schema.
        Includes extracted patient_info (name, age, gender, DOB, report_date).

    Raises:
        AnalysisError: If analysis fails after all retries.
    """
    settings = get_settings()
    prompt_template = load_prompt_template()

    # Format the prompt with patient context
    age_str = str(age) if age is not None else "Not provided"
    gender_str = gender if gender else "Not provided"

    prompt = prompt_template.format(
        age=age_str,
        gender=gender_str,
        ocr_text=ocr_text[:8000],  # Cap text length for context window
    )

    logger.info(
        f"Starting LLM analysis with {settings.llm_analysis_model} "
        f"(age={age_str}, gender={gender_str}, text_len={len(ocr_text)})"
    )

    llm = get_analysis_llm()

    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            response_text = response.content.strip()

            result = parse_analysis_response(response_text)
            validate_analysis_structure(result)

            logger.info(
                f"LLM analysis complete: {len(result.get('categories', []))} categories, "
                f"summary_len={len(result.get('summary', ''))}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1}: "
                f"Failed to parse LLM JSON response: {e}"
            )
            if attempt == max_retries:
                raise AnalysisError(
                    "Failed to analyze report: LLM response was not valid JSON."
                )

        except AnalysisError:
            raise

        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1}: "
                f"Analysis error: {e}"
            )
            if attempt == max_retries:
                raise AnalysisError(f"Failed to analyze report: {e}")

    raise AnalysisError("Analysis failed after all retries.")


def parse_analysis_response(response_text: str) -> dict:
    """Parse the LLM's JSON response, handling markdown code blocks.

    Args:
        response_text: Raw text response from LLM.

    Returns:
        Parsed dict.
    """
    json_text = response_text

    # Strip markdown code blocks if present
    if "```json" in json_text:
        json_text = json_text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in json_text:
        json_text = json_text.split("```", 1)[1].split("```", 1)[0]

    return json.loads(json_text.strip())


def validate_analysis_structure(data: dict) -> None:
    """Validate the analysis JSON has the required top-level keys.

    Args:
        data: Parsed analysis dict.

    Raises:
        AnalysisError: If required keys are missing.
    """
    required_keys = ["patient_info", "summary", "categories"]
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise AnalysisError(
            f"LLM response missing required keys: {missing}"
        )

    if not isinstance(data["categories"], list):
        raise AnalysisError("'categories' must be a list")
