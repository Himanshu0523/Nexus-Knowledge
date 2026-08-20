from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime

class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentUploadResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    message: str

class DocumentStatusResponse(BaseModel):
    document_id: str
    status: DocumentStatus
    filename: str
    file_size: int
    chunks_created: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ChunkMetadata(BaseModel):
    document_id: str
    chunk_id: str
    page: Optional[int] = None
    source: str
    tenant_id: str
    chunk_index: int
    total_chunks: int
    text: str

class RAGContext(BaseModel):
    chunks: List[ChunkMetadata]
    sources: List[Dict[str, Any]]
    relevance_scores: List[float]

class ChatRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    stream: bool = False
    knowledge_base_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    response: str
    sources: Optional[List[Dict[str, Any]]] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = "qwen"
