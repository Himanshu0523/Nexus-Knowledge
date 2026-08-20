from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    stream: bool = False
    metadata: Optional[Dict[str, Any]] = None

class UsageInfo(BaseModel):
    input_tokens: int
    output_tokens: int

class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    response: str
    usage: Optional[UsageInfo] = None
    model: Optional[str] = "qwen"