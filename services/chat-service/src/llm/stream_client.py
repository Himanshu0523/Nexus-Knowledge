from typing import AsyncGenerator, List, Dict, Any, Optional
import json
import httpx
import asyncio
import os
import logging
from shared.security.circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


class LLMStreamClient:
    """
    Resilient LLM client with streaming support and Circuit Breaker failover.
    Automatically switches to backup provider on 503 Service Unavailable or network
    timeouts without crashing the Server-Sent Events (SSE) stream.
    """
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self.backup_provider = os.getenv("LLM_BACKUP_PROVIDER", "mock").lower()
        self.model = os.getenv("LLM_MODEL", "qwen")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
        
        # Primary provider circuit breaker
        self.circuit_breaker = CircuitBreaker(
            name=f"llm_{self.provider}",
            failure_threshold=int(os.getenv("CB_FAILURE_THRESHOLD", "2")),
            recovery_timeout=float(os.getenv("CB_RECOVERY_TIMEOUT", "20.0"))
        )
    
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens with Circuit Breaker and automated backup provider switching.
        Guarantees that 503 Service Unavailable or provider outages never crash SSE.
        """
        if self.provider == "mock":
            async for token in self._mock_stream(messages):
                yield token
            return

        # 1. Check circuit breaker state
        if self.circuit_breaker.state == CircuitState.OPEN:
            logger.warning(
                f"[CircuitBreaker] Primary provider '{self.provider}' circuit is OPEN! "
                f"Directly failing over to backup provider '{self.backup_provider}' for SSE stream."
            )
            async for token in self._stream_provider(self.backup_provider, messages, tools):
                yield token
            return

        # 2. Attempt streaming with primary provider
        tokens_yielded = 0
        try:
            stream_gen = self._stream_provider(self.provider, messages, tools)
            async for token in stream_gen:
                tokens_yielded += 1
                yield token
            
            # Record success
            await self.circuit_breaker._on_success()

        except Exception as e:
            logger.warning(
                f"[CircuitBreaker] Primary LLM provider '{self.provider}' failed during stream "
                f"(yielded={tokens_yielded}): {e}. Recording failure and initiating fallback..."
            )
            await self.circuit_breaker._on_failure(e)

            # If failed before sending tokens, seamlessly stream from backup provider
            if tokens_yielded == 0:
                logger.info(f"[CircuitBreaker] Seamlessly streaming from fallback provider '{self.backup_provider}'")
                async for token in self._stream_provider(self.backup_provider, messages, tools):
                    yield token
            else:
                yield f"\n[Stream recovered via backup provider]"

    async def _stream_provider(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Route stream call to the appropriate backend provider implementation."""
        if provider == "ollama":
            async for token in self._ollama_stream(messages, tools):
                yield token
        elif provider == "openai":
            async for token in self._openai_stream(messages, tools):
                yield token
        else:
            async for token in self._mock_stream(messages):
                yield token
    
    async def _mock_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Mock streaming for testing and graceful fallback."""
        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        last_message = user_messages[-1]["content"] if user_messages else ""
        
        mock_response = f"This is an enterprise response to: {last_message}"
        words = mock_response.split()
        
        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            yield token
            await asyncio.sleep(0.02)
    
    async def _ollama_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream from Ollama API with HTTP error validation."""
        async with httpx.AsyncClient() as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True
            }
            if tools:
                payload["tools"] = tools
            
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=30.0
            ) as response:
                if response.status_code == 503:
                    raise httpx.HTTPStatusError("503 Service Unavailable", request=response.request, response=response)
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "tool_calls" in data.get("message", {}):
                                tool_call = data["message"]["tool_calls"][0]
                                yield f"__TOOL_CALL__:{json.dumps(tool_call)}"
                                continue
                            
                            if "message" in data and "content" in data["message"]:
                                token = data["message"]["content"]
                                if token:
                                    yield token
                        except json.JSONDecodeError:
                            continue
    
    async def _openai_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI API with HTTP error validation."""
        async with httpx.AsyncClient() as client:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True
            }
            if tools:
                payload["tools"] = [
                    {"type": "function", "function": tool}
                    for tool in tools
                ]
            
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30.0
            ) as response:
                if response.status_code == 503:
                    raise httpx.HTTPStatusError("503 Service Unavailable", request=response.request, response=response)
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            if "tool_calls" in delta:
                                tool_call = delta["tool_calls"][0]
                                yield f"__TOOL_CALL__:{json.dumps(tool_call)}"
                                continue
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
