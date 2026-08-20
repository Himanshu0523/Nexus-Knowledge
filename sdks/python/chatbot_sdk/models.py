from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[float] = None

class DocumentSource(BaseModel):
    document: str
    page: Optional[int] = None
    relevance_score: Optional[float] = None

class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    response: str
    sources: Optional[List[DocumentSource]] = []
    usage: Optional[UsageInfo] = None
    model: Optional[str] = "qwen"

    @property
    def text(self) -> str:
        return self.response

class StreamEvent(BaseModel):
    type: str
    event_id: Optional[str] = None
    timestamp: Optional[float] = None
    content: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    source: Optional[str] = None
    page: Optional[int] = None
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    message_id: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
