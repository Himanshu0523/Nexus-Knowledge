import asyncio
import time
from typing import AsyncGenerator, Dict, Any, Optional
from .base import BaseLLMAdapter
from ..models import BackendConfig, LLMRequest, LLMResponse, StreamChunk

class MockAdapter(BaseLLMAdapter):
    """
    Mock LLM Adapter used for unit testing, offline execution,
    and emergency fallback when external backends are offline.
    """

    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        
        user_messages = [msg for msg in request.messages if msg.get("role") == "user"]
        last_message = user_messages[-1]["content"] if user_messages else ""
        
        # Check for tool test keywords or rule-based replies
        tool_calls = None
        if "weather in" in last_message.lower():
            tool_calls = [{
                "id": "call_mock_1",
                "type": "function",
                "function": {
                    "name": "weather",
                    "arguments": '{"location": "Tokyo"}'
                }
            }]
            content = ""
        else:
            content = f"Mock response for [{request.tenant_id}]: {last_message}"

        latency_ms = (time.time() - start_time) * 1000.0
        prompt_tokens = sum(len(m.get("content", "")) for m in request.messages) // 4
        completion_tokens = len(content) // 4

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model_used=self.config.model_name,
            backend_used=self.config.name,
            prompt_tokens=max(1, prompt_tokens),
            completion_tokens=max(1, completion_tokens),
            total_tokens=max(2, prompt_tokens + completion_tokens),
            latency_ms=latency_ms,
            fallback_occurred=False
        )

    async def stream(self, request: LLMRequest) -> AsyncGenerator[StreamChunk, None]:
        user_messages = [msg for msg in request.messages if msg.get("role") == "user"]
        last_message = user_messages[-1]["content"] if user_messages else ""

        full_text = f"Mock response for [{request.tenant_id}]: {last_message}"
        words = full_text.split()

        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            yield StreamChunk(
                delta=token,
                model_used=self.config.model_name,
                backend_used=self.config.name,
                is_final=(i == len(words) - 1)
            )
            await asyncio.sleep(0.01)

    async def check_health(self) -> bool:
        return True
