import json
import time
import httpx
from typing import AsyncGenerator, Dict, Any, Optional
from .base import BaseLLMAdapter
from ..models import BackendConfig, LLMRequest, LLMResponse, StreamChunk

class OllamaAdapter(BaseLLMAdapter):
    """
    Ollama Backend Adapter.
    Ollama provides lightweight local serving for development, edge, and single-host models.
    Supports /api/chat streaming and function tools.
    """

    def _get_url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{base}{path}"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        url = self._get_url("/api/chat")

        payload = {
            "model": request.model if request.model != "default" else self.config.model_name,
            "messages": request.messages,
            "stream": False,
            "options": {
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "top_p": request.top_p if request.top_p is not None else 0.9,
            }
        }

        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        if request.tools:
            payload["tools"] = request.tools

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.time() - start_time) * 1000.0
        msg = data.get("message", {})
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls")

        prompt_tokens = data.get("prompt_eval_count", sum(len(m.get("content", "")) for m in request.messages) // 4)
        completion_tokens = data.get("eval_count", len(content) // 4)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model_used=payload["model"],
            backend_used=self.config.name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            fallback_occurred=False
        )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        url = self._get_url("/api/chat")

        payload = {
            "model": request.model if request.model != "default" else self.config.model_name,
            "messages": request.messages,
            "stream": True,
            "options": {
                "temperature": request.temperature if request.temperature is not None else 0.7,
                "top_p": request.top_p if request.top_p is not None else 0.9,
            }
        }

        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        if request.tools:
            payload["tools"] = request.tools

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            msg = data.get("message", {})
                            token = msg.get("content") or ""
                            tool_calls = msg.get("tool_calls")
                            done = data.get("done", False)

                            yield StreamChunk(
                                delta=token,
                                tool_calls=tool_calls,
                                is_final=done,
                                model_used=payload["model"],
                                backend_used=self.config.name,
                                finish_reason="stop" if done else None
                            )
                        except json.JSONDecodeError:
                            continue

    async def check_health(self) -> bool:
        url = self._get_url("/api/tags")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False
