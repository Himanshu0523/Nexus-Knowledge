from typing import List, Dict, Any, Optional
import os
import httpx
import json

class LLMService:
    def __init__(self):
        # For Phase 3, we'll use a mock LLM service
        # In production, integrate with actual LLM API
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model = os.getenv("LLM_MODEL", "qwen")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    
    async def generate_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Generate response using LLM"""
        if self.llm_provider == "mock":
            return await self._mock_llm_response(messages)
        elif self.llm_provider == "openai":
            return await self._openai_response(messages)
        else:
            return await self._mock_llm_response(messages)
    
    async def _mock_llm_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Mock LLM for testing Phase 3"""
        # Get the last user message
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        last_user_message = user_messages[-1]["content"] if user_messages else ""
        
        # Check if we have conversation context
        has_context = len(messages) > 2  # More than system + current message
        
        # Simple rule-based responses for testing
        responses = {
            "what is python": "Python is a high-level, interpreted programming language known for its simplicity and readability. It's widely used in web development, data science, AI, and automation.",
            "who created it": "Python was created by Guido van Rossum and first released in 1991.",
            "who created python": "Python was created by Guido van Rossum and first released in 1991.",
            "what is machine learning": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
            "hello": "Hello! How can I help you today?",
            "hi": "Hi there! What can I do for you?",
        }
        
        # Simple contextual response
        response_text = responses.get(
            last_user_message.lower().strip(),
            f"Echo: {last_user_message}"
        )
        
        # If we have context, try to provide more contextual response
        if has_context and "it" in last_user_message.lower():
            # Find previous topic
            for msg in reversed(messages[:-1]):
                if msg["role"] == "user":
                    prev_topic = msg["content"].lower()
                    if "python" in prev_topic:
                        response_text = "Python was created by Guido van Rossum and first released in 1991."
                        break
        
        return {
            "response": response_text,
            "model": self.model,
            "usage": {
                "input_tokens": len(str(messages)) // 4,
                "output_tokens": len(response_text) // 4
            }
        }
    
    async def _openai_response(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Call OpenAI API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "response": data["choices"][0]["message"]["content"],
                    "model": self.model,
                    "usage": {
                        "input_tokens": data["usage"]["prompt_tokens"],
                        "output_tokens": data["usage"]["completion_tokens"]
                    }
                }
            else:
                # Fallback to mock on error
                return await self._mock_llm_response(messages)