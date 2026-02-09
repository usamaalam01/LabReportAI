"""Chat service for post-analysis Q&A.

Provides streaming responses about lab report results with rate limiting per report.
"""
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import redis.asyncio as redis
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.services.llm_provider import get_chat_llm

logger = logging.getLogger(__name__)

# Load prompt template
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def load_chat_prompt() -> str:
    """Load the chat prompt template."""
    prompt_path = PROMPTS_DIR / "chat.txt"
    return prompt_path.read_text(encoding="utf-8")


class ChatLimitExceeded(Exception):
    """Raised when chat message limit is reached for a report."""

    def __init__(self, message: str = "Message limit reached for this report."):
        self.message = message
        super().__init__(self.message)


class ChatService:
    """Service for generating chat responses about lab report results."""

    def __init__(self, analysis_json: dict, job_id: str):
        self.analysis = analysis_json
        self.job_id = job_id
        self.prompt_template = load_chat_prompt()

    def _build_prompt(
        self, message: str, history: list[dict]
    ) -> str:
        """Build the full prompt with context, history, and user message."""
        # Format conversation history
        history_text = ""
        if history:
            history_lines = []
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role}: {msg['content']}")
            history_text = "\n".join(history_lines)
        else:
            history_text = "(No previous messages)"

        # Format analysis JSON (pretty print for readability)
        analysis_text = json.dumps(self.analysis, indent=2, ensure_ascii=False)

        return self.prompt_template.format(
            analysis_json=analysis_text,
            history=history_text,
            message=message,
        )

    async def generate_response_stream(
        self, message: str, history: list[dict]
    ) -> AsyncGenerator[str, None]:
        """Stream chat response tokens."""
        prompt = self._build_prompt(message, history)
        llm = get_chat_llm()

        try:
            async for chunk in llm.astream([HumanMessage(content=prompt)]):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"Chat LLM error: {e}")
            yield "I'm sorry, I encountered an error. Please try again."

    def generate_response_sync(
        self, message: str, history: list[dict]
    ) -> str:
        """Generate a complete response (non-streaming, for follow-up generation)."""
        prompt = self._build_prompt(message, history)
        llm = get_chat_llm()

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.error(f"Chat LLM error: {e}")
            return "I'm sorry, I encountered an error. Please try again."

    def generate_starter_suggestions(self) -> list[str]:
        """Generate starter questions based on analysis results."""
        suggestions = []

        # Extract abnormal/critical values from categories
        abnormal_tests = []
        categories_with_issues = set()

        for category in self.analysis.get("categories", []):
            category_name = category.get("name", "")
            for test in category.get("tests", []):
                severity = test.get("severity", "normal")
                if severity in ("borderline", "critical"):
                    abnormal_tests.append({
                        "name": test.get("test_name", ""),
                        "severity": severity,
                        "category": category_name,
                    })
                    categories_with_issues.add(category_name)

        # Generate questions based on findings
        if abnormal_tests:
            # Priority 1: Questions about critical/borderline values
            critical = [t for t in abnormal_tests if t["severity"] == "critical"]
            borderline = [t for t in abnormal_tests if t["severity"] == "borderline"]

            if critical:
                test = critical[0]
                suggestions.append(
                    f"What does my {test['severity']} {test['name']} level mean?"
                )

            if borderline and len(suggestions) < 2:
                test = borderline[0]
                suggestions.append(
                    f"Should I be concerned about my {test['name']}?"
                )

            # Priority 2: Lifestyle improvement questions
            if "Lipid" in str(categories_with_issues):
                suggestions.append(
                    "What dietary changes can help improve my cholesterol?"
                )
            elif "CBC" in str(categories_with_issues) or "Blood" in str(categories_with_issues):
                suggestions.append(
                    "How can I improve my blood health naturally?"
                )
            elif "Liver" in str(categories_with_issues):
                suggestions.append(
                    "What lifestyle changes support liver health?"
                )
            elif "Kidney" in str(categories_with_issues):
                suggestions.append(
                    "How can I support my kidney function?"
                )
            elif "Thyroid" in str(categories_with_issues):
                suggestions.append(
                    "What factors affect thyroid health?"
                )
            else:
                suggestions.append(
                    "What lifestyle changes do you recommend based on my results?"
                )

        # Fallback generic questions if no abnormal values
        if len(suggestions) < 3:
            generic = [
                "Give me an overview of my lab results.",
                "Are there any values I should pay attention to?",
                "What do my results mean overall?",
                "Should I discuss any results with my doctor?",
            ]
            for q in generic:
                if len(suggestions) >= 4:
                    break
                if q not in suggestions:
                    suggestions.append(q)

        return suggestions[:4]  # Max 4 suggestions

    def generate_followup_suggestions(
        self, last_question: str, last_response: str
    ) -> list[str]:
        """Generate contextual follow-up suggestions."""
        suggestions = []
        last_q_lower = last_question.lower()
        last_r_lower = last_response.lower()

        # Detect topics discussed
        discussed_cholesterol = any(
            w in last_q_lower or w in last_r_lower
            for w in ["cholesterol", "ldl", "hdl", "lipid", "triglyceride"]
        )
        discussed_blood = any(
            w in last_q_lower or w in last_r_lower
            for w in ["hemoglobin", "rbc", "wbc", "platelet", "anemia", "cbc"]
        )
        discussed_liver = any(
            w in last_q_lower or w in last_r_lower
            for w in ["liver", "alt", "ast", "bilirubin", "albumin"]
        )
        discussed_kidney = any(
            w in last_q_lower or w in last_r_lower
            for w in ["kidney", "creatinine", "bun", "egfr", "urea"]
        )
        discussed_thyroid = any(
            w in last_q_lower or w in last_r_lower
            for w in ["thyroid", "tsh", "t3", "t4"]
        )
        discussed_diet = any(
            w in last_q_lower or w in last_r_lower
            for w in ["diet", "food", "eat", "nutrition"]
        )
        discussed_exercise = any(
            w in last_q_lower or w in last_r_lower
            for w in ["exercise", "physical", "workout", "activity"]
        )

        # Generate relevant follow-ups
        if discussed_cholesterol:
            if not discussed_diet:
                suggestions.append("What foods should I eat to lower cholesterol?")
            if not discussed_exercise:
                suggestions.append("How does exercise affect cholesterol levels?")
            suggestions.append("Tell me about my other lipid values.")

        elif discussed_blood:
            suggestions.append("What foods are rich in iron?")
            suggestions.append("What causes low hemoglobin levels?")

        elif discussed_liver:
            suggestions.append("What foods support liver health?")
            suggestions.append("What can damage the liver?")

        elif discussed_kidney:
            suggestions.append("How much water should I drink daily?")
            suggestions.append("What foods are good for kidney health?")

        elif discussed_thyroid:
            suggestions.append("What affects thyroid function?")
            suggestions.append("Are there foods that support thyroid health?")

        elif discussed_diet and not discussed_exercise:
            suggestions.append("What exercise routine do you recommend?")

        elif discussed_exercise and not discussed_diet:
            suggestions.append("What dietary changes would complement my exercise?")

        # Always offer to discuss other results
        if len(suggestions) < 3:
            suggestions.append("What other results should I know about?")

        # Generic helpful follow-ups
        if len(suggestions) < 2:
            suggestions.extend([
                "Should I follow up with my doctor?",
                "What tests might I need in the future?",
            ])

        return suggestions[:3]  # Max 3 follow-ups


# Redis functions for chat rate limiting
_redis_client: redis.Redis | None = None


async def get_chat_redis() -> redis.Redis:
    """Get or create the async Redis client for chat."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url, decode_responses=True
        )
    return _redis_client


async def check_chat_limit(job_id: str) -> tuple[bool, int]:
    """Check if user can send more messages for this report.

    Returns:
        Tuple of (allowed, remaining_messages)
    """
    settings = get_settings()
    key = f"chat_count:{job_id}"

    client = await get_chat_redis()
    count = await client.get(key)
    count = int(count) if count else 0

    remaining = settings.chat_message_limit - count
    return remaining > 0, max(remaining, 0)


async def increment_chat_count(job_id: str) -> int:
    """Increment message count for a report, return remaining messages."""
    settings = get_settings()
    key = f"chat_count:{job_id}"

    client = await get_chat_redis()
    count = await client.incr(key)

    if count == 1:
        # Set TTL on first message (same as report retention)
        await client.expire(key, settings.retention_period * 60 * 60)

    remaining = settings.chat_message_limit - count
    return max(remaining, 0)


async def get_remaining_messages(job_id: str) -> int:
    """Get remaining message count for a report."""
    _, remaining = await check_chat_limit(job_id)
    return remaining
