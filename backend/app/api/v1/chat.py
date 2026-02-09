"""Chat API endpoints for post-analysis Q&A.

Provides SSE streaming responses about lab report results.
"""
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.report import Report, ReportStatus
from app.schemas.chat import ChatMessageRequest, ChatSuggestionsResponse
from app.services.chat import (
    ChatLimitExceeded,
    ChatService,
    check_chat_limit,
    get_remaining_messages,
    increment_chat_count,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_report_analysis(
    job_id: str, db: AsyncSession
) -> tuple[Report | None, dict | None]:
    """Get report and parsed analysis JSON."""
    result = await db.execute(
        select(Report).where(Report.job_id == job_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        return None, None

    if not report.result_json:
        return report, None

    try:
        analysis = json.loads(report.result_json)
        return report, analysis
    except json.JSONDecodeError:
        logger.error(f"Failed to parse analysis JSON for job_id={job_id}")
        return report, None


@router.get(
    "/{job_id}/suggestions",
    response_model=ChatSuggestionsResponse,
)
async def get_chat_suggestions(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get starter question suggestions for a completed report."""
    settings = get_settings()

    if not settings.chat_enabled:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "code": 503, "message": "Chat feature is disabled."},
        )

    report, analysis = await get_report_analysis(job_id, db)

    if not report:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": 404, "message": "Report not found."},
        )

    if report.status != ReportStatus.COMPLETED:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": "Report analysis not yet complete."},
        )

    if not analysis:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": "Analysis results not available."},
        )

    remaining = await get_remaining_messages(job_id)
    chat_service = ChatService(analysis, job_id)
    suggestions = chat_service.generate_starter_suggestions()

    return ChatSuggestionsResponse(
        suggestions=suggestions,
        messages_remaining=remaining,
    )


@router.post("/{job_id}")
async def send_chat_message(
    job_id: str,
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a chat message and receive streaming response.

    Returns SSE stream with tokens, then final event with suggestions.
    """
    settings = get_settings()

    if not settings.chat_enabled:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "code": 503, "message": "Chat feature is disabled."},
        )

    # Validate message length
    if len(request.message) > settings.chat_max_message_length:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "code": 400,
                "message": f"Message exceeds {settings.chat_max_message_length} character limit.",
            },
        )

    # Check rate limit before processing
    allowed, remaining = await check_chat_limit(job_id)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "status": "error",
                "code": 429,
                "message": f"Message limit ({settings.chat_message_limit}) reached for this report.",
            },
        )

    report, analysis = await get_report_analysis(job_id, db)

    if not report:
        return JSONResponse(
            status_code=404,
            content={"status": "error", "code": 404, "message": "Report not found."},
        )

    if report.status != ReportStatus.COMPLETED:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": "Report analysis not yet complete."},
        )

    if not analysis:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "code": 400, "message": "Analysis results not available."},
        )

    # Increment count (do this before streaming starts)
    new_remaining = await increment_chat_count(job_id)

    chat_service = ChatService(analysis, job_id)

    # Convert history to list of dicts
    history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

    async def generate_sse():
        """Generate SSE stream with tokens and final event."""
        full_response = ""

        try:
            async for token in chat_service.generate_response_stream(
                request.message, history
            ):
                full_response += token
                # Send token event
                data = json.dumps({"content": token})
                yield f"event: token\ndata: {data}\n\n"

            # Generate follow-up suggestions
            followups = chat_service.generate_followup_suggestions(
                request.message, full_response
            )

            # Send done event with suggestions and remaining count
            done_data = json.dumps({
                "suggestions": followups,
                "messages_remaining": new_remaining,
            })
            yield f"event: done\ndata: {done_data}\n\n"

        except Exception as e:
            logger.error(f"Chat streaming error: {e}")
            error_data = json.dumps({"message": "An error occurred during response generation."})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
