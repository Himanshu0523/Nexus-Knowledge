from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
import httpx
import json
import os

router = APIRouter()

CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")

@router.post("/chat/stream")
async def chat_stream(request: Request):
    """Stream chat response using SSE"""
    try:
        body = await request.json()
        
        async def generate():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{CHAT_SERVICE_URL}/api/v1/chat/stream",
                    json=body,
                    timeout=300.0
                ) as response:
                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            if line:
                                yield f"{line}\n"
                    else:
                        error_event = {
                            "type": "error",
                            "code": "UPSTREAM_ERROR",
                            "message": f"Chat service returned {response.status_code}"
                        }
                        yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
        
    except Exception as e:
        return {"error": str(e)}
