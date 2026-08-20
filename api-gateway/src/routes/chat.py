from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import uuid

from middleware.auth import verify_api_key

router = APIRouter()

# ── Schemas ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)
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

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail

# ── Endpoint ─────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    api_key: str = Depends(verify_api_key)
):
    """Process a chat message and return a response."""
    try:
        message_id = f"msg_{uuid.uuid4().hex[:10]}"
        mock_response = f"Echo: {request.message}"

        return ChatResponse(
            conversation_id=request.conversation_id,
            message_id=message_id,
            response=mock_response,
            usage=UsageInfo(
                input_tokens=len(request.message.split()),
                output_tokens=len(mock_response.split())
            ),
            model="qwen"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": str(e),
                    "request_id": getattr(req.state, "request_id", None)
                }
            }
        )