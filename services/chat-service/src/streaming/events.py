from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import uuid
import json

class StreamEventType(str, Enum):
    """Types of stream events"""
    STATUS = "status"
    TOKEN = "token"
    SOURCE = "source"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    DONE = "done"
    METADATA = "metadata"

class StreamStatus(str, Enum):
    """Stream status values"""
    STARTED = "started"
    PROCESSING = "processing"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    TOOL_EXECUTING = "tool_executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StreamEvent(BaseModel):
    """Base stream event model"""
    type: StreamEventType
    timestamp: float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:10]}")
    
    def to_sse(self) -> str:
        """Convert to SSE format"""
        data = json.dumps(self.dict())
        return f"data: {data}\n\n"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "timestamp": self.timestamp,
            "event_id": self.event_id
        }

class StatusEvent(StreamEvent):
    """Status update event"""
    status: StreamStatus
    message: Optional[str] = None
    
    def __init__(self, status: StreamStatus, message: Optional[str] = None, **kwargs):
        super().__init__(type=StreamEventType.STATUS, **kwargs)
        self.status = status
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["status"] = self.status.value if isinstance(self.status, Enum) else self.status
        if self.message:
            data["message"] = self.message
        return data

class TokenEvent(StreamEvent):
    """Token chunk event"""
    content: str
    token_index: Optional[int] = None
    
    def __init__(self, content: str, token_index: Optional[int] = None, **kwargs):
        super().__init__(type=StreamEventType.TOKEN, **kwargs)
        self.content = content
        self.token_index = token_index
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["content"] = self.content
        if self.token_index is not None:
            data["token_index"] = self.token_index
        return data

class SourceEvent(StreamEvent):
    """Source citation event"""
    document_id: Optional[str] = None
    source: Optional[str] = None
    page: Optional[int] = None
    relevance_score: Optional[float] = None
    chunk_id: Optional[str] = None
    
    def __init__(self, **kwargs):
        super().__init__(type=StreamEventType.SOURCE, **kwargs)
        self.document_id = kwargs.get("document_id")
        self.source = kwargs.get("source")
        self.page = kwargs.get("page")
        self.relevance_score = kwargs.get("relevance_score")
        self.chunk_id = kwargs.get("chunk_id")
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["document_id"] = self.document_id
        data["source"] = self.source
        data["page"] = self.page
        data["relevance_score"] = self.relevance_score
        data["chunk_id"] = self.chunk_id
        return data

class ToolStartEvent(StreamEvent):
    """Tool execution start event"""
    tool_name: str
    arguments: Dict[str, Any] = {}
    
    def __init__(self, tool_name: str, arguments: Dict[str, Any] = {}, **kwargs):
        super().__init__(type=StreamEventType.TOOL_START, **kwargs)
        self.tool_name = tool_name
        self.arguments = arguments
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["tool_name"] = self.tool_name
        data["arguments"] = self.arguments
        return data

class ToolResultEvent(StreamEvent):
    """Tool execution result event"""
    tool_name: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    
    def __init__(self, tool_name: str, status: str, result: Dict[str, Any] = None, error: str = None, execution_time: float = None, **kwargs):
        super().__init__(type=StreamEventType.TOOL_RESULT, **kwargs)
        self.tool_name = tool_name
        self.status = status
        self.result = result
        self.error = error
        self.execution_time = execution_time
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["tool_name"] = self.tool_name
        data["status"] = self.status
        if self.result:
            data["result"] = self.result
        if self.error:
            data["error"] = self.error
        if self.execution_time:
            data["execution_time"] = self.execution_time
        return data

class ErrorEvent(StreamEvent):
    """Error event"""
    code: str
    message: str
    
    def __init__(self, code: str, message: str, **kwargs):
        super().__init__(type=StreamEventType.ERROR, **kwargs)
        self.code = code
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["code"] = self.code
        data["message"] = self.message
        return data

class DoneEvent(StreamEvent):
    """Stream completion event"""
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    status: StreamStatus = StreamStatus.COMPLETED
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    
    def __init__(self, message_id: str = None, conversation_id: str = None, status: StreamStatus = StreamStatus.COMPLETED, usage: Dict[str, int] = None, model: str = None, **kwargs):
        super().__init__(type=StreamEventType.DONE, **kwargs)
        self.message_id = message_id
        self.conversation_id = conversation_id
        self.status = status
        self.usage = usage
        self.model = model
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["status"] = self.status.value if isinstance(self.status, Enum) else self.status
        if self.message_id:
            data["message_id"] = self.message_id
        if self.conversation_id:
            data["conversation_id"] = self.conversation_id
        if self.usage:
            data["usage"] = self.usage
        if self.model:
            data["model"] = self.model
        return data

class MetadataEvent(StreamEvent):
    """Metadata event for additional information"""
    metadata: Dict[str, Any] = {}
    
    def __init__(self, metadata: Dict[str, Any], **kwargs):
        super().__init__(type=StreamEventType.METADATA, **kwargs)
        self.metadata = metadata
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["metadata"] = self.metadata
        return data
