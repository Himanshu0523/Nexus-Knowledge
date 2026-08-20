from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
import uuid
from datetime import datetime

from models.database_models import User, Conversation, Message
from database.redis_client import redis_client

class ConversationService:
    def __init__(self, db: Session):
        self.db = db
        self.redis = redis_client
    
    def get_or_create_user(self, external_id: Optional[str] = None) -> User:
        """Get or create a user"""
        if not external_id:
            external_id = f"anonymous_{uuid.uuid4().hex[:10]}"
        
        user = self.db.query(User).filter(User.external_id == external_id).first()
        if not user:
            user = User(external_id=external_id)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    def get_or_create_conversation(self, conversation_id: str, user_id: Optional[int] = None) -> Conversation:
        """Get or create a conversation"""
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            # Auto-generate title from first message
            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title="New Conversation"
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)
        
        return conversation
    
    def add_message(self, conversation_id: str, role: str, content: str, model: Optional[str] = None) -> Message:
        """Add a message to both PostgreSQL and Redis"""
        message_id = f"msg_{uuid.uuid4().hex[:10]}"
        
        # Save to PostgreSQL
        message = Message(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model
        )
        self.db.add(message)
        
        # Update conversation timestamp
        conversation = self.db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        if conversation:
            conversation.updated_at = datetime.utcnow()
            # Auto-update title if this is the first user message
            if role == 'user' and conversation.title == "New Conversation":
                conversation.title = content[:50] + ('...' if len(content) > 50 else '')
        
        self.db.commit()
        self.db.refresh(message)
        
        # Save to Redis
        redis_message = {
            "role": role,
            "content": content,
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.redis.add_message(conversation_id, redis_message)
        
        return message
    
    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get conversation history from PostgreSQL"""
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(desc(Message.created_at)).limit(limit).all()
        
        # Reverse to chronological order
        messages.reverse()
        return [msg.to_dict() for msg in messages]
    
    def get_recent_context(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent context from Redis (fast)"""
        return self.redis.get_recent_messages(conversation_id, limit)
    
    def clear_conversation_cache(self, conversation_id: str):
        """Clear conversation from Redis cache"""
        self.redis.clear_conversation(conversation_id)
    
    def rebuild_conversation_cache(self, conversation_id: str, limit: int = 20):
        """Rebuild Redis cache from PostgreSQL data"""
        messages = self.get_conversation_history(conversation_id, limit)
        
        context = []
        for msg in messages:
            context.append({
                "role": msg["role"],
                "content": msg["content"],
                "message_id": msg["id"],
                "timestamp": msg["created_at"]
            })
        
        self.redis.set_conversation_context(conversation_id, context)