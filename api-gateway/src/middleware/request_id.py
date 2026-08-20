from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from shared.security.request_id import generate_request_id

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that injects X-Request-ID into state and response headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
