from pydantic import BaseModel, Field


class ChatMessageHistory(BaseModel):
    """A single message in conversation history."""

    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    message: str = Field(..., min_length=1, max_length=500)
    conversation_history: list[ChatMessageHistory] = Field(default_factory=list)


class ChatSuggestionsResponse(BaseModel):
    """Response for getting starter/follow-up suggestions."""

    suggestions: list[str]
    messages_remaining: int
