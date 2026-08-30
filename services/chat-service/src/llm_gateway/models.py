from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid
import time

class BackendType(str, Enum):
    VLLM = "vllm"
    OLLAMA = "ollama"
    OPENAI = "openai"
    MOCK = "mock"

class BackendStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

@dataclass
class BackendConfig:
    name: str
    type: BackendType
    base_url: str
    api_key: str = ""
    model_name: str = "default"
    max_context_length: int = 8192
    weight: int = 100
    timeout_seconds: float = 30.0
    is_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TenantPolicy:
    tenant_id: str
    tier: str = "standard"  # free, standard, enterprise
    primary_backend: Optional[str] = None
    allowed_models: List[str] = field(default_factory=lambda: ["*"])
    max_context_length: int = 4096
    max_tokens_per_request: int = 1024
    monthly_token_budget: Optional[int] = None
    default_temperature: float = 0.7
    default_top_p: float = 0.9

@dataclass
class LLMRequest:
    messages: List[Dict[str, str]]
    tenant_id: str = "default"
    user_role: str = "member"
    model: str = "default"
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None
    stream: bool = False
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class LLMResponse:
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    model_used: str = "default"
    backend_used: str = "mock"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    fallback_occurred: bool = False
    attempt_history: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class StreamChunk:
    delta: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    is_final: bool = False
    model_used: Optional[str] = None
    backend_used: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
