import logging
import time
from fastapi import Request
from typing import Callable
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def logging_middleware(request: Request, call_next: Callable):
    """Middleware to log all requests and responses"""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Get request body (careful with large bodies)
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if len(body) < 10000:  # Only log if body is less than 10KB
                logger.debug(f"Request body: {body.decode()}")
        except Exception:
            pass
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} "
        f"Process time: {process_time:.3f}s "
        f"Request ID: {getattr(request.state, 'request_id', 'N/A')}"
    )
    
    return response