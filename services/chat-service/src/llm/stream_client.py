from typing import AsyncGenerator, List, Dict, Any, Optional
import json
import httpx
import asyncio
import os

class LLMStreamClient:
    """LLM client with streaming support"""
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "mock")
        self.model = os.getenv("LLM_MODEL", "qwen")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    
    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens"""
        if self.provider == "mock":
            async for token in self._mock_stream(messages):
                yield token
        elif self.provider == "ollama":
            async for token in self._ollama_stream(messages, tools):
                yield token
        elif self.provider == "openai":
            async for token in self._openai_stream(messages, tools):
                yield token
        else:
            async for token in self._mock_stream(messages):
                yield token
    
    async def _mock_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Mock streaming for testing"""
        # Get last user message
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        last_message = user_messages[-1]["content"] if user_messages else ""
        
        # Generate mock response
        mock_response = f"This is a mock streaming response to: {last_message}"
        
        # Split into tokens (words)
        words = mock_response.split()
        
        for i, word in enumerate(words):
            # Add space before word (except first)
            token = word if i == 0 else f" {word}"
            yield token
            await asyncio.sleep(0.05)  # Simulate streaming delay
    
    async def _ollama_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream from Ollama API"""
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
                timeout=60.0
            ) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                
                                # Check for tool calls
                                if "tool_calls" in data.get("message", {}):
                                    # Handle tool call in stream
                                    tool_call = data["message"]["tool_calls"][0]
                                    # Yield special marker for tool call
                                    yield f"__TOOL_CALL__:{json.dumps(tool_call)}"
                                    continue
                                
                                # Extract token
                                if "message" in data and "content" in data["message"]:
                                    token = data["message"]["content"]
                                    if token:
                                        yield token
                                        
                            except json.JSONDecodeError:
                                continue
                else:
                    # Fallback to mock
                    async for token in self._mock_stream(messages):
                        yield token
    
    async def _openai_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream from OpenAI API"""
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
                timeout=60.0
            ) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            
                            if data_str.strip() == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                
                                # Check for tool calls
                                if "tool_calls" in data.get("choices", [{}])[0].get("delta", {}):
                                    tool_call = data["choices"][0]["delta"]["tool_calls"][0]
                                    yield f"__TOOL_CALL__:{json.dumps(tool_call)}"
                                    continue
                                
                                # Extract token
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                                    
                            except json.JSONDecodeError:
                                continue
                else:
                    # Fallback to mock
                    async for token in self._mock_stream(messages):
                        yield token
