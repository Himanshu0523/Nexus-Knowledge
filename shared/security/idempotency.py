import json
import logging
from typing import Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis

logger = logging.getLogger(__name__)


class IdempotencyManager:
    """Manages idempotency states in Redis/Valkey with in-memory fallback."""

    def __init__(self, redis_client=None, prefix: str = "idempotency", ttl: int = 86400, lock_ttl: int = 60):
        self.redis_client = redis_client
        self.prefix = prefix
        self.ttl = ttl
        self.lock_ttl = lock_ttl
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _make_key(self, idempotency_key: str) -> str:
        return f"{self.prefix}:{idempotency_key}"

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        full_key = self._make_key(key)
        if self.redis_client and hasattr(self.redis_client, "get"):
            try:
                client = getattr(self.redis_client, "client", self.redis_client)
                val = client.get(full_key)
                if val:
                    if isinstance(val, bytes):
                        val = val.decode("utf-8")
                    return json.loads(val)
            except Exception as e:
                logger.warning(f"Redis get idempotency key failed: {e}")
        
        return self._memory_cache.get(full_key)

    def set_processing(self, key: str) -> bool:
        full_key = self._make_key(key)
        data = json.dumps({"status": "PROCESSING"})
        
        if self.redis_client and hasattr(self.redis_client, "get"):
            try:
                client = getattr(self.redis_client, "client", self.redis_client)
                # Use lock_ttl (e.g. 60s) for PROCESSING state to prevent deadlocks on worker crashes
                is_set = client.set(full_key, data, ex=self.lock_ttl, nx=True)
                return bool(is_set)
            except Exception as e:
                logger.warning(f"Redis set_processing failed: {e}")

        if full_key in self._memory_cache:
            return False
        self._memory_cache[full_key] = {"status": "PROCESSING"}
        return True

    def save_completed(self, key: str, status_code: int, body: Any):
        full_key = self._make_key(key)
        data = json.dumps({
            "status": "COMPLETED",
            "status_code": status_code,
            "body": body
        })

        if self.redis_client and hasattr(self.redis_client, "get"):
            try:
                client = getattr(self.redis_client, "client", self.redis_client)
                client.setex(full_key, self.ttl, data)
                return
            except Exception as e:
                logger.warning(f"Redis save_completed failed: {e}")

        self._memory_cache[full_key] = {
            "status": "COMPLETED",
            "status_code": status_code,
            "body": body
        }

    def delete(self, key: str):
        full_key = self._make_key(key)
        if self.redis_client and hasattr(self.redis_client, "get"):
            try:
                client = getattr(self.redis_client, "client", self.redis_client)
                client.delete(full_key)
                return
            except Exception as e:
                logger.warning(f"Redis delete idempotency key failed: {e}")

        self._memory_cache.pop(full_key, None)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware that checks Idempotency-Key header for POST/PUT requests.
    Prevents duplicate executions and returns cached responses for replayed requests.
    """

    def __init__(self, app, manager: IdempotencyManager):
        super().__init__(app)
        self.manager = manager

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            return await call_next(request)

        existing = self.manager.get(idempotency_key)
        if existing:
            if existing.get("status") == "PROCESSING":
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": {
                            "code": "CONCURRENT_REQUEST",
                            "message": "A request with this Idempotency-Key is currently being processed.",
                            "idempotency_key": idempotency_key
                        }
                    }
                )
            elif existing.get("status") == "COMPLETED":
                return JSONResponse(
                    status_code=existing.get("status_code", 200),
                    content=existing.get("body"),
                    headers={
                        "X-Cache": "HIT",
                        "X-Idempotent-Replay": "true",
                        "Idempotency-Key": idempotency_key
                    }
                )

        # Acquire lock / set status to PROCESSING
        acquired = self.manager.set_processing(idempotency_key)
        if not acquired:
            return JSONResponse(
                status_code=409,
                content={
                    "error": {
                        "code": "CONCURRENT_REQUEST",
                        "message": "A request with this Idempotency-Key is currently being processed.",
                        "idempotency_key": idempotency_key
                    }
                }
            )

        try:
            response = await call_next(request)

            content_type = response.headers.get("content-type", "")

            # If response is successful and JSON, capture body and cache it
            if response.status_code < 400 and content_type.startswith("application/json"):
                # Intercept response body
                response_body = [section async for section in response.body_iterator]
                response.body_iterator = _async_iter(response_body)
                try:
                    full_body = b"".join(response_body).decode("utf-8")
                    json_data = json.loads(full_body)
                    self.manager.save_completed(idempotency_key, response.status_code, json_data)
                except Exception as exc:
                    logger.warning(f"Could not parse body for idempotency caching: {exc}")
            elif response.status_code >= 400:
                self.manager.delete(idempotency_key)

            response.headers["Idempotency-Key"] = idempotency_key
            return response
        except Exception:
            self.manager.delete(idempotency_key)
            raise


async def _async_iter(items: list):
    """Converts a list of byte chunks into an async generator for Starlette body_iterator compatibility."""
    for item in items:
        yield item

