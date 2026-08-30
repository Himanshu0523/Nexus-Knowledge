import json
import time
import httpx
from typing import AsyncGenerator, Dict, Any, Optional
from .base import BaseLLMAdapter
from ..models import BackendConfig, LLMRequest, LLMResponse, StreamChunk

class OpenAIAdapter(BaseLLMAdapter):
    """
    OpenAI Cloud Backend Adapter.
    Communicates with OpenAI API or OpenAI-compatible cloud proxies (/v1/chat/completions).
    """

    def _get_url(self, path: str) -> str:
        base = self.config.base_url.rstrip("/")
        if not path.startswith("/"):
            path = f"/{path}"
        if not base.endswith("/v1") and path.startswith("/chat/completions"):
            base = f"{base}/v1"
        return f"{base}{path}"

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        url = self._get_url("/chat/completions")
        headers = self._get_headers()

        payload = {
            "model": request.model if request.model != "default" else self.config.model_name,
            "messages": request.messages,
            "temperature": request.temperature if request.temperature is not None else 0.7,
            "top_p": request.top_p if request.top_p is not None else 0.9,
            "stream": False,
        }

        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": tool} if "function" not in tool else tool
                for tool in request.tools
            ]

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.time() - start_time) * 1000.0
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

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
        url = self._get_url("/chat/completions")
        headers = self._get_headers()

        payload = {
            "model": request.model if request.model != "default" else self.config.model_name,
            "messages": request.messages,
            "temperature": request.temperature if request.temperature is not None else 0.7,
            "top_p": request.top_p if request.top_p is not None else 0.9,
            "stream": True,
        }

        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens

        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": tool} if "function" not in tool else tool
                for tool in request.tools
            ]

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            yield StreamChunk(
                                delta="",
                                is_final=True,
                                model_used=payload["model"],
                                backend_used=self.config.name,
                                finish_reason="stop"
                            )
                            break
                        try:
                            data = json.loads(data_str)
                            choice = data.get("choices", [{}])[0]
                            delta = choice.get("delta", {})
                            token = delta.get("content") or ""
                            tool_calls = delta.get("tool_calls")
                            finish_reason = choice.get("finish_reason")

                            yield StreamChunk(
                                delta=token,
                                tool_calls=tool_calls,
                                is_final=(finish_reason is not None and finish_reason != ""),
                                model_used=payload["model"],
                                backend_used=self.config.name,
                                finish_reason=finish_reason
                            )
                        except json.JSONDecodeError:
                            continue

    async def check_health(self) -> bool:
        url = self._get_url("/models")
        headers = self._get_headers()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                return resp.status_code == 200
        except Exception:
            return False
