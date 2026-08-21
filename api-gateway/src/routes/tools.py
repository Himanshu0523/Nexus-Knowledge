from fastapi import APIRouter, Request, HTTPException
import httpx
import os

router = APIRouter()

CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8001")

@router.get("/tools")
async def get_tools(request: Request):
    """
    Get all active tools available to the LLM agent.
    Returns the real tools configured in the chat service.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CHAT_SERVICE_URL}/api/v1/tools",
                timeout=5.0
            )
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=response.json())
    except httpx.ConnectTimeout:
        raise HTTPException(
            status_code=504,
            detail={"error": {"code": "TIMEOUT", "message": "Connection to Chat Service timed out"}}
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "SERVICE_UNAVAILABLE", "message": f"Service unavailable: {str(e)}"}}
        )
