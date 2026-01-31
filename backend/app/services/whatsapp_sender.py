"""Twilio WhatsApp message sender service.

Optional — gracefully skips when Twilio keys are empty or "placeholder".
"""
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


class WhatsAppError(Exception):
    """Raised when WhatsApp message sending fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def is_whatsapp_enabled() -> bool:
    """Check if Twilio WhatsApp is configured (not empty/placeholder)."""
    settings = get_settings()
    sid = settings.twilio_account_sid
    token = settings.twilio_auth_token
    return (
        bool(sid) and sid != "placeholder"
        and bool(token) and token != "placeholder"
    )


def send_whatsapp_message(to: str, body: str) -> None:
    """Send a WhatsApp text message via Twilio.

    Args:
        to: Recipient phone number (e.g., "+923001234567").
        body: Message text (truncated to 1600 chars for WhatsApp).
    """
    if not is_whatsapp_enabled():
        logger.warning("WhatsApp not configured — skipping send")
        return

    from twilio.rest import Client

    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    message = client.messages.create(
        from_=f"whatsapp:{settings.twilio_whatsapp_number}",
        to=f"whatsapp:{to}",
        body=body[:1600],
    )
    logger.info(f"WhatsApp message sent: sid={message.sid}, to={to}")


def send_whatsapp_pdf(to: str, body: str, pdf_url: str) -> None:
    """Send a WhatsApp message with PDF attachment via Twilio.

    Args:
        to: Recipient phone number.
        body: Message text.
        pdf_url: Publicly accessible URL of the PDF.
    """
    if not is_whatsapp_enabled():
        logger.warning("WhatsApp not configured — skipping send")
        return

    from twilio.rest import Client

    settings = get_settings()
    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    message = client.messages.create(
        from_=f"whatsapp:{settings.twilio_whatsapp_number}",
        to=f"whatsapp:{to}",
        body=body[:1600],
        media_url=[pdf_url],
    )
    logger.info(f"WhatsApp PDF sent: sid={message.sid}, to={to}")
