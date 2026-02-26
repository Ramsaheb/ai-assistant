from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    """A single message in conversation history."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class QueryRequest(BaseModel):
    """Incoming question from a user."""
    question: str = Field(
        ..., min_length=3, max_length=500,
        description="Business question to answer",
        examples=["What is the total pipeline value?"],
    )
    conversation_history: list[ConversationMessage] = Field(
        default_factory=list,
        description="Previous messages for follow-up context (max 10)",
    )


class TraceItem(BaseModel):
    """Single entry in the agent's chain-of-thought trace."""
    timestamp: str
    message: str


class ClarifyingQuestion(BaseModel):
    """A clarifying question the agent wants to ask."""
    question: str
    suggestions: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    """Full response returned to the user."""
    answer: str
    trace: list[TraceItem]
    data_quality_issues: list[str] = Field(default_factory=list)
    clarifying_question: ClarifyingQuestion | None = Field(
        default=None,
        description="If the query is ambiguous, the agent may ask a clarifying question",
    )