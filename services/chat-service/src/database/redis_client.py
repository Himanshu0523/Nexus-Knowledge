import redis
import json
from typing import List, Dict, Any, Optional
import os

class RedisClient:
    def __init__(self):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(os.getenv("REDIS_DB", 0))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        
        self.client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            password=self.redis_password,
            decode_responses=True
        )
        
        # Cache expiration time (in seconds) - 24 hours
        self.expiration_time = 24 * 60 * 60
    
    def get_recent_messages(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages from Redis cache"""
        key = f"conversation:{conversation_id}:recent"
        
        try:
            # Get from Redis list (most recent last)
            messages_json = self.client.lrange(key, -limit, -1)
            messages = [json.loads(msg) for msg in messages_json]
            return messages
        except redis.RedisError as e:
            print(f"Redis error: {e}")
            return []
    
    def add_message(self, conversation_id: str, message: Dict[str, Any], max_size: int = 20):
        """Add a message to Redis cache"""
        key = f"conversation:{conversation_id}:recent"
        
        try:
            # Add message to list
            self.client.rpush(key, json.dumps(message))
            
            # Trim to max size
            self.client.ltrim(key, -max_size, -1)
            
            # Set expiration
            self.client.expire(key, self.expiration_time)
        except redis.RedisError as e:
            print(f"Redis error: {e}")
    
    def set_conversation_context(self, conversation_id: str, context: List[Dict[str, Any]]):
        """Set full conversation context in Redis"""
        key = f"conversation:{conversation_id}:recent"
        
        try:
            # Clear existing list
            self.client.delete(key)
            
            # Add all messages
            if context:
                for message in context:
                    self.client.rpush(key, json.dumps(message))
                
                # Set expiration
                self.client.expire(key, self.expiration_time)
        except redis.RedisError as e:
            print(f"Redis error: {e}")
    
    def clear_conversation(self, conversation_id: str):
        """Clear conversation from Redis"""
        key = f"conversation:{conversation_id}:recent"
        
        try:
            self.client.delete(key)
        except redis.RedisError as e:
            print(f"Redis error: {e}")
    
    def cache_response(self, cache_key: str, response: Any, expiration: int = 3600):
        """Cache a response for quick retrieval"""
        try:
            self.client.setex(
                f"cache:{cache_key}",
                expiration,
                json.dumps(response)
            )
        except redis.RedisError as e:
            print(f"Redis error: {e}")
    
    def get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response"""
        try:
            cached = self.client.get(f"cache:{cache_key}")
            if cached:
                return json.loads(cached)
            return None
        except redis.RedisError as e:
            print(f"Redis error: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check Redis connection"""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False

# Singleton instance
redis_client = RedisClient()