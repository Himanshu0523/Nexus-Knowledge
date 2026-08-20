from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, BigInteger, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    api_key_hash = Column(String(255), nullable=False)
    api_key_prefix = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    plan = Column(String(50), default="free")
    
    users = relationship("User", back_populates="tenant")
    conversations = relationship("Conversation", back_populates="tenant")
    api_keys = relationship("APIKey", back_populates="tenant")

class APIKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(String(50), primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey('tenants.id'), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    tenant = relationship("Tenant", back_populates="api_keys")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey('tenants.id'), nullable=False, index=True)
    external_id = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    tenant = relationship("Tenant", back_populates="users")
    conversations = relationship("Conversation", back_populates="user")
    
    __table_args__ = (
        Index('idx_user_tenant_id', 'tenant_id', 'id'),
    )

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(String(50), primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    title = Column(String(255), default="New Conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    tenant = relationship("Tenant", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_conversation_tenant_id', 'tenant_id', 'id'),
    )

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(String(50), primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey('tenants.id'), nullable=False, index=True)
    conversation_id = Column(String(50), ForeignKey('conversations.id'), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    model = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")
    
    __table_args__ = (
        Index('idx_message_tenant_conversation', 'tenant_id', 'conversation_id'),
    )

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(String(50), primary_key=True, index=True)
    tenant_id = Column(String(50), ForeignKey('tenants.id'), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    status = Column(String(20), default="pending")
    chunks_created = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_document_tenant_id', 'tenant_id', 'id'),
    )