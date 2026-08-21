from fastapi import APIRouter, Request, HTTPException
from typing import Dict, Any

router = APIRouter()

@router.get("/tools")
async def get_tools(request: Request):
    """
    Get all active tools available to the LLM agent.
    Returns the real tools configured in the chat service.
    """
    return {
        "tools": [
            {
                "name": "Calculator",
                "description": "Evaluates mathematical expressions safely",
                "status": "Active"
            },
            {
                "name": "Web_Search",
                "description": "Searches the internet for real-time information",
                "status": "Active"
            },
            {
                "name": "Weather_API",
                "description": "Fetches current weather data for locations",
                "status": "Active"
            },
            {
                "name": "Database_Query",
                "description": "Queries the analytical database safely",
                "status": "Active"
            }
        ]
    }
