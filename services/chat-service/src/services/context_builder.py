from typing import List, Dict, Any, Optional
from database.redis_client import redis_client
from services.conversation_service import ConversationService

class ContextBuilder:
    def __init__(self, conversation_service: ConversationService):
        self.conversation_service = conversation_service
        self.redis = redis_client
        self.max_context_length = 4000  # Maximum tokens for context
    
    def build_context(self, conversation_id: str, current_message: str) -> List[Dict[str, str]]:
        """Build context for LLM"""
        # Try to get recent context from Redis first (fast path)
        recent_messages = self.conversation_service.get_recent_context(
            conversation_id, 
            limit=10
        )
        
        # If Redis is empty (cache miss), get from PostgreSQL
        if not recent_messages:
            history = self.conversation_service.get_conversation_history(
                conversation_id, 
                limit=10
            )
            recent_messages = [
                {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                for msg in history
            ]
        
        # Build LLM context
        llm_messages = []
        
        # Add system message
        llm_messages.append({
            "role": "system",
            "content": "You are a helpful AI assistant. Use the conversation history to provide contextual responses. Always be concise and accurate."
        })
        
        # Add recent conversation history
        llm_messages.extend(recent_messages)
        
        # Add current message if not already included
        if current_message and (not llm_messages or llm_messages[-1].get("content") != current_message):
            llm_messages.append({
                "role": "user",
                "content": current_message
            })
        
        # Trim context if too long
        return self._trim_context(llm_messages)
    
    def _trim_context(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Trim context to fit within token limits"""
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        
        # Simple estimation: 1 token ≈ 4 characters
        estimated_tokens = total_chars / 4
        
        if estimated_tokens <= self.max_context_length:
            return messages
        
        # Remove oldest messages (except system message) until within limits
        while estimated_tokens > self.max_context_length and len(messages) > 2:
            # Keep system message and last message
            removed = messages.pop(1)
            total_chars = sum(len(msg.get("content", "")) for msg in messages)
            estimated_tokens = total_chars / 4
        
        return messages
    
    def extract_key_information(self, conversation_id: str) -> Dict[str, Any]:
        """Extract key information from conversation for enhanced context"""
        history = self.conversation_service.get_conversation_history(conversation_id, limit=50)
        
        # Simple information extraction (can be enhanced with NLP later)
        info = {
            "topics": set(),
            "entities": set(),
            "last_question": None,
            "total_messages": len(history)
        }
        
        for msg in history:
            if msg["role"] == "user":
                info["last_question"] = msg["content"]
                # Simple topic extraction (capitalized words)
                words = msg["content"].split()
                for word in words:
                    if word[0].isupper() and len(word) > 1:
                        info["entities"].add(word)
        
        info["topics"] = list(info["topics"])
        info["entities"] = list(info["entities"])
        
        return info