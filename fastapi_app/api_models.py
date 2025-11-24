from enum import Enum
from typing import Any, Optional

from openai.types.chat import ChatCompletionMessageParam
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class AIChatRoles(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    content: str
    role: AIChatRoles = AIChatRoles.USER


class RetrievalMode(str, Enum):
    TEXT = "text"
    VECTORS = "vectors"
    HYBRID = "hybrid"


class ChatRequestOverrides(BaseModel):
    top: int = 3
    temperature: float = 0.3
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    use_advanced_flow: bool = True
    prompt_template: Optional[str] = None
    seed: Optional[int] = None


class ChatRequestContext(BaseModel):
    overrides: ChatRequestOverrides


class ChatRequest(BaseModel):
    messages: list[ChatCompletionMessageParam]
    context: ChatRequestContext
    sessionState: Optional[Any] = None
    conversation_id: Optional[str] = None


class ThoughtStep(BaseModel):
    title: str
    description: Any
    props: dict[str, Any] = {}


class RAGContext(BaseModel):
    data_points: dict[str | int, dict[str, Any]]
    thoughts: list[ThoughtStep]
    followup_questions: Optional[list[str]] = None


class ErrorResponse(BaseModel):
    error: str


class RetrievalResponse(BaseModel):
    message: Message
    context: RAGContext
    sessionState: Optional[Any] = None


class RetrievalResponseDelta(BaseModel):
    delta: Optional[Message] = None
    context: Optional[RAGContext] = None
    sessionState: Optional[Any] = None


class ItemPublic(BaseModel):
    id: int
    file_name: str
    description: str


class ItemWithDistance(ItemPublic):
    distance: float

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.distance = round(self.distance, 2)


class ChatParams(ChatRequestOverrides):
    prompt_template: str
    response_token_limit: int = 1024
    enable_text_search: bool
    enable_vector_search: bool
    original_user_query: str
    past_messages: list[ChatCompletionMessageParam]


class ConversationMessagePublic(BaseModel):
    message_id: str
    conversation_id: str
    message_role: str
    message_content: str
    message_timestamp: str


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ConversationMessagePublic]


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for user profile updates."""

    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserPublic(UserBase):
    """Public user schema (returned in API responses)."""

    id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload schema."""

    sub: str  # User ID
    exp: datetime
    iat: datetime
    type: str  # "access" or "refresh"


class LoginRequest(BaseModel):
    """Login request schema."""

    username: str  # Can be username or email
    password: str


class RefreshTokenRequest(BaseModel):
    """Token refresh request schema."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Password change request schema."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
