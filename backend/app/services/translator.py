"""LLM-based translation service for lab report analysis results.

Translates the structured JSON analysis from English to Urdu
while preserving JSON structure, numeric values, and severity fields.
"""
import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.services.llm_provider import get_translation_llm

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "translation.txt"


class TranslationError(Exception):
    """Raised when LLM translation fails after retries."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def translate_analysis(analysis: dict, max_retries: int = 2) -> dict:
    """Translate English analysis JSON to Urdu via LLM.

    Args:
        analysis: English analysis dict from LLM analyzer.
        max_retries: Number of retry attempts on failure.

    Returns:
        Translated dict with identical structure but Urdu text.

    Raises:
        TranslationError: If translation fails after all retries.
    """
    if not PROMPT_PATH.exists():
        raise TranslationError(f"Translation prompt not found: {PROMPT_PATH}")

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    result_json = json.dumps(analysis, ensure_ascii=False, indent=2)
    prompt = prompt_template.format(result_json=result_json)

    logger.info(f"Starting translation (json_len={len(result_json)})")

    llm = get_translation_llm()

    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            response_text = response.content.strip()

            translated = _parse_json_response(response_text)
            _validate_translation(translated)

            logger.info(
                f"Translation complete: {len(translated.get('categories', []))} categories"
            )
            return translated

        except json.JSONDecodeError as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1}: "
                f"Failed to parse translation JSON: {e}"
            )
            if attempt == max_retries:
                raise TranslationError(
                    f"Translation returned invalid JSON: {e}"
                )

        except TranslationError:
            raise

        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries + 1}: "
                f"Translation error: {e}"
            )
            if attempt == max_retries:
                raise TranslationError(f"Translation failed: {e}")

    raise TranslationError("Translation failed after all retries.")


def _parse_json_response(text: str) -> dict:
    """Parse the LLM's JSON response, handling markdown code blocks."""
    json_text = text

    if "```json" in json_text:
        json_text = json_text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in json_text:
        json_text = json_text.split("```", 1)[1].split("```", 1)[0]

    return json.loads(json_text.strip())


def _validate_translation(translated: dict) -> None:
    """Validate the translated JSON has required top-level keys."""
    required_keys = ["patient_info", "summary", "categories"]
    missing = [k for k in required_keys if k not in translated]
    if missing:
        raise TranslationError(
            f"Translated JSON missing required keys: {missing}"
        )

    if not isinstance(translated["categories"], list):
        raise TranslationError("'categories' must be a list")
