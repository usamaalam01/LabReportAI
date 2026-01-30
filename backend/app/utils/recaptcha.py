"""Google reCAPTCHA v3 verification.

Optional: skipped when RECAPTCHA_SECRET_KEY is empty or "placeholder".
"""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


class RecaptchaError(Exception):
    """Raised when reCAPTCHA verification fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def is_recaptcha_enabled() -> bool:
    """Check if reCAPTCHA is configured (not empty/placeholder)."""
    settings = get_settings()
    key = settings.recaptcha_secret_key
    return bool(key) and key != "placeholder"


async def verify_recaptcha(token: str, min_score: float = 0.5) -> None:
    """Verify reCAPTCHA v3 token. Raises RecaptchaError on failure.

    No-op if reCAPTCHA is not configured (development mode).
    """
    if not is_recaptcha_enabled():
        return

    if not token:
        raise RecaptchaError("reCAPTCHA token is required.")

    settings = get_settings()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                VERIFY_URL,
                data={
                    "secret": settings.recaptcha_secret_key,
                    "response": token,
                },
            )
            result = resp.json()
    except Exception as e:
        logger.warning(f"reCAPTCHA verification request failed: {e}")
        raise RecaptchaError("reCAPTCHA verification unavailable.")

    if not result.get("success"):
        raise RecaptchaError("reCAPTCHA verification failed.")

    score = result.get("score", 0)
    if score < min_score:
        raise RecaptchaError(f"reCAPTCHA score too low: {score}")

    logger.debug(f"reCAPTCHA verified: score={score}")
