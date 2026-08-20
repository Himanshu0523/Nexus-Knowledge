from fastapi import HTTPException, Request
from typing import Dict, Tuple
import time
from collections import defaultdict
import os

class RateLimiter:
    """Simple in-memory rate limiter for Phase 1"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
    
    def check_rate_limit(self, key: str) -> None:
        """Check if the request should be rate limited"""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[key] = [req_time for req_time in self.requests[key] if req_time > minute_ago]
        
        # Check if rate limit exceeded
        if len(self.requests[key]) >= self.requests_per_minute:
            retry_after = int(60 - (now - self.requests[key][0]))
            raise HTTPException(
                status_code=429,
                detail={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded. Try again in {retry_after} seconds",
                        "retry_after": retry_after
                    }
                },
                headers={"Retry-After": str(retry_after)}
            )
        
        # Add current request
        self.requests[key].append(now)

# Initialize rate limiter
rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
)

async def rate_limit_middleware(request: Request, call_next):
    """Middleware to apply rate limiting"""
    # Get client identifier (API key or IP address)
    client_id = getattr(request.state, "api_key", None) or request.client.host
    
    try:
        rate_limiter.check_rate_limit(client_id)
    except HTTPException as e:
        return e
    
    response = await call_next(request)
    return response